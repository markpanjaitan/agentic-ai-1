import pymysql
import re
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env file
# This is crucial for securely managing your API keys and other configurations.
load_dotenv()

# ------------------------
# 🔍 Get DB schema
# ------------------------
def get_db_schema(cursor):
    """
    Introspects the MySQL database to retrieve schema information.
    Args:
        cursor: A pymysql cursor object connected to the database.
    Returns:
        A formatted string representing the database schema.
    """
    schema = ""

    # Fetch all tables in the current database
    cursor.execute("SHOW TABLES")
    
    # Handle both DictCursor and regular cursor cases for tables
    tables = []
    fetched_tables = cursor.fetchall()
    if fetched_tables:
        if isinstance(fetched_tables[0], dict):
            # For DictCursor (keys are column names)
            db_name = os.getenv('MYSQL_DATABASE', 'SchoolDb')
            tables = [row["Tables_in_" + db_name] for row in fetched_tables]
        else:
            # For regular cursor (numeric indices)
            tables = [row[0] for row in fetched_tables]

    # For each table, fetch its columns and their data types
    for table in tables:
        # Use backticks for table names to handle special characters or reserved words
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        columns = cursor.fetchall()
        schema += f"Table: {table}\n"
        
        # Handle both DictCursor and regular cursor for columns
        for column in columns:
            if isinstance(column, dict):  # DictCursor case
                column_name = column["Field"]
                data_type = column["Type"]
            else:  # Regular cursor case
                column_name = column[0]
                data_type = column[1]
                
            schema += f"- {column_name} ({data_type})\n"
        schema += "\n"
    return schema.strip()

# ------------------------
# 🧠 Build LLM prompt (now returns a list of contents for Gemini API)
# ------------------------
def build_prompt(user_question, schema, error_message=None, previous_sql=None):
    """
    Constructs the prompt messages for the LLM, including schema, user question,
    and optionally error messages for re-attempts.
    Args:
        user_question (str): The user's natural language question.
        schema (str): The database schema.
        error_message (str, optional): An error message from a previous failed query.
        previous_sql (str, optional): The SQL query that previously failed.
    Returns:
        list: A list of message dictionaries in Gemini's API 'contents' format.
    """
    # The system instructions are now explicitly part of the initial user message,
    # as Gemini's `generate_content` doesn't have a separate `system` role parameter.
    # We structure it clearly within the 'user' part.
    
    system_instruction = """
You are a SQL expert. You will receive a database schema and a user question.
Your task is to generate a valid MySQL SELECT query that answers the user's question.

You MUST adhere to these rules:
- Use ONLY table and column names exactly as provided in the schema.
- NEVER invent or singularize table names (e.g., use 'Students' if that's in the schema, not 'Student').
- Output ONLY a valid MySQL SELECT statement, ending with a semicolon.
- Do NOT include any explanations, comments, or additional text outside of the SQL query.
- Use backticks (`) for quoting identifiers if they contain special characters or are reserved words.
- Use LIMIT instead of TOP for row limiting.
"""

    user_message_content = f"""
Schema:
{schema}

Question: "{user_question}"

Output:
"""

    if error_message:
        user_message_content = f"""
You previously generated this SQL which failed:

{previous_sql}

The error was:
{error_message}

Try again. ONLY use the tables and columns listed in this schema.

{user_message_content}
"""
    
    # Gemini's `generate_content` expects a list of parts, typically one text part for a simple prompt
    contents = [
        {"role": "user", "parts": [{"text": system_instruction + "\n\n" + user_message_content}]}
    ]
    
    return contents

# ------------------------
# 🧼 Extract SELECT statement
# ------------------------
def extract_valid_sql(text):
    """
    Extracts a valid SQL SELECT statement from the LLM's response.
    Validates for MySQL compatibility.
    Args:
        text (str): The raw text response from the LLM.
    Returns:
        str: The extracted and validated SQL query.
    Raises:
        ValueError: If no valid SELECT statement is found or if invalid keywords are present.
    """
    # Use re.DOTALL to allow '.' to match newlines, important for multi-line SQL
    match = re.search(r"(SELECT\s.+?;)", text, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("No valid SELECT statement found in LLM response.")
    sql = match.group(1).strip()
    
    # Basic MySQL specific validation
    if "TOP" in sql.upper():
        raise ValueError("Invalid keyword 'TOP' for MySQL. Use LIMIT instead.")
    
    return sql

# ------------------------
# 🚀 MAIN SCRIPT
# ------------------------

# Step 0: Connect to MySQL (credentials now from .env)
try:
    conn = pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        port=int(os.getenv('MYSQL_PORT', '3306')),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE', 'SchoolDb'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor # Use DictCursor to get results as dictionaries
    )
    cursor = conn.cursor()
    print("MySQL database connection successful.")
except pymysql.Error as ex:
    print(f"MySQL connection failed: {ex}")
    print("Please ensure MySQL is running, the database exists, and credentials are correct in your .env file.")
    exit() # Exit if database connection fails

# Step 1: Configure Google Gemini client
# Get API key from environment variable, which was loaded by dotenv
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please set it in your .env file.")

genai.configure(api_key=GEMINI_API_KEY)

# Choose a suitable Gemini model. 'gemini-1.5-flash' is generally a good choice for speed and capability.
# You can override this in your .env file with GEMINI_MODEL=gemini-1.0-pro or other available models.
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
model = genai.GenerativeModel(GEMINI_MODEL)
print(f"Gemini client initialized with model: {GEMINI_MODEL}")

# Step 2: User question
# user_question = "Find the names of all students who have a score higher than 150."
user_question = "Find the names of all students who's first name starts with J."
print(f"\nUser Question: \"{user_question}\"")

# Step 3: Introspect schema
print("\nIntrospecting database schema...")
schema = get_db_schema(cursor)
print("Schema retrieved successfully.")
# print("\nSchema:\n", schema, "\n") # Added newline for better readability

# Step 4: Attempt loop
MAX_RETRIES = 2
attempt = 0
error_message = None
sql_query = None
data = None

while attempt < MAX_RETRIES:
    print(f"\n--- Attempt {attempt + 1} ---")
    # Build prompt contents for Gemini API
    prompt_contents = build_prompt(user_question, schema, error_message, sql_query)
    print("\nprompt_contents:\n", prompt_contents, "\n")
    
    try:
        # Call Gemini API
        response = model.generate_content(
            prompt_contents, # Pass the list of contents
            generation_config={"max_output_tokens": 200} # Adjust max_output_tokens as needed for SQL query length
        )
        
        # Extract the text content from the Gemini response
        # Access .text directly for simple text responses
        raw_response = response.text.strip()
            
        print(f"🔍 LLM Raw Response:\n{raw_response}")

        sql_query = extract_valid_sql(raw_response)
        print("✅ Extracted SQL:\n", sql_query)

        # Execute the SQL query against the database
        cursor.execute(sql_query)
        data = cursor.fetchall()  # Using DictCursor so we get dictionaries directly

        if not data:
            raise ValueError("Query ran successfully but returned no results.")

        print("Query executed successfully.")
        break  # ✅ Success: Exit loop if query runs and returns data

    except ValueError as ve:
        # Handle errors related to SQL extraction or empty results
        error_message = str(ve)
        print("🚨 Validation Error:", error_message)
        attempt += 1
    except pymysql.Error as pe:
        # Handle database execution errors
        error_message = f"MySQL Error: {pe}"
        print("🚨 MySQL Error:", error_message)
        attempt += 1
    except genai.types.BlockedPromptException as bpe:
        # Handle cases where the prompt was blocked by safety filters
        error_message = f"Gemini API Error: Prompt was blocked - {bpe}"
        print("🚨 Gemini API Error:", error_message)
        attempt += 1
    except genai.types.APIError as gae:
        # Handle general Gemini API errors (e.g., invalid API key, rate limits, model not found)
        error_message = f"Gemini API Error: {gae}"
        print("🚨 Gemini API Error:", error_message)
        attempt += 1
    except Exception as e:
        # Catch any other unexpected errors
        error_message = str(e)
        print("🚨 Unexpected Error:", error_message)
        attempt += 1

# Step 5: Summarize or report failure
if data:
    print("\n--- Final Result ---")
    # Build prompt for summarization for Gemini
    summary_prompt_text = f"""
Here are the results of the query:\n{data}
Summarize this nicely for the user.
"""
    summary_contents = [{"role": "user", "parts": [{"text": summary_prompt_text}]}]

    try:
        summary_response = model.generate_content(
            summary_contents, # Pass the list of contents
            generation_config={"max_output_tokens": 200} # Adjust max_output_tokens for summary length
        )
        summary = summary_response.text.strip()
        print("📄 Summary:\n", summary)
    except Exception as e:
        print(f"Failed to generate summary: {e}")
        print("Raw Data:", data) # Fallback to printing raw data if summary fails
else:
    print("\n❌ Failed after retries. Please rephrase your question or check the database/schema.")

# Close the database connection
if 'conn' in locals() and conn:
    conn.close()
    print("Database connection closed.")