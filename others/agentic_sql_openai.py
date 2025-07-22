import pymysql
import re
import os
from dotenv import load_dotenv
from openai import OpenAI  # Changed from anthropic to openai

# Load environment variables from .env file
load_dotenv()

# ------------------------
# 🔍 Get DB schema (Updated for MySQL)
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
    
    # Handle both DictCursor and regular cursor cases
    try:
        # For DictCursor (keys are column names)
        tables = [row["Tables_in_" + os.getenv('MYSQL_DATABASE', 'SchoolDb')] for row in cursor.fetchall()]
    except KeyError:
        # For regular cursor (numeric indices)
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]

    # For each table, fetch its columns and their data types
    for table in tables:
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")  # Added backticks for safety
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
# 🧠 Build LLM prompt (updated for MySQL compatibility)
# ------------------------
def build_prompt(user_question, schema, error_message=None, previous_sql=None):
    """
    Constructs the prompt messages for the LLM, now with MySQL-specific guidance.
    """
    system_message = """
You are a SQL expert. You will receive a database schema and a user question.
Your task is to generate a valid MySQL SELECT query that answers the user's question.

You MUST adhere to these rules:
- Use ONLY table and column names exactly as provided in the schema.
- NEVER invent or singularize table names (e.g., use 'Students' if that's in the schema, not 'Student').
- Output ONLY a valid MySQL SELECT statement, ending with a semicolon.
- Do NOT include any explanations, comments, or additional text outside of the SQL query.
- Use backticks (`) for quoting identifiers if they contain special characters.
- Use LIMIT instead of TOP for row limiting.
"""

    user_message = f"""
Schema:
{schema}

Question: "{user_question}"

Output:
"""

    if error_message:
        user_message = f"""
You previously generated this SQL which failed:

{previous_sql}

The error was:
{error_message}

Try again. ONLY use the tables and columns listed in this schema.

{user_message}
"""
    
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

# ------------------------
# 🧼 Extract SELECT statement (updated for MySQL)
# ------------------------
def extract_valid_sql(text):
    """
    Extracts a valid SQL SELECT statement from the LLM's response.
    Now validates for MySQL compatibility.
    """
    match = re.search(r"(SELECT\s.+?;)", text, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("No valid SELECT statement found in LLM response.")
    sql = match.group(1).strip()
    
    # Basic MySQL validation
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
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()
    print("MySQL database connection successful.")
except pymysql.Error as ex:
    print(f"MySQL connection failed: {ex}")
    print("Please ensure MySQL is running, the database exists, and credentials are correct.")
    exit()

# Step 1: Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found. Please set it in your .env file.")

client = OpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo")  # Default to gpt-4-turbo
print(f"OpenAI client initialized with model: {OPENAI_MODEL}")

# Step 2: User question
user_question = "Find the names of all students who have a score higher than 150."
print(f"\nUser Question: \"{user_question}\"")

# Step 3: Introspect schema
print("\nIntrospecting database schema...")
schema = get_db_schema(cursor)
print("Schema retrieved successfully.")

# Step 4: Attempt loop
MAX_RETRIES = 2
attempt = 0
error_message = None
sql_query = None
data = None

while attempt < MAX_RETRIES:
    print(f"\n--- Attempt {attempt + 1} ---")
    messages = build_prompt(user_question, schema, error_message, sql_query)
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=200,
            temperature=0.3  # Lower temperature for more deterministic SQL generation
        )
        raw_response = response.choices[0].message.content.strip()
        print(f"🔍 LLM Raw Response:\n{raw_response}")

        sql_query = extract_valid_sql(raw_response)
        print("✅ Extracted SQL:\n", sql_query)

        # Execute the SQL query
        cursor.execute(sql_query)
        data = cursor.fetchall()

        if not data:
            raise ValueError("Query ran successfully but returned no results.")

        print("Query executed successfully.")
        break

    except ValueError as ve:
        error_message = str(ve)
        print("🚨 Validation Error:", error_message)
        attempt += 1
    except pymysql.Error as pe:
        error_message = f"MySQL Error: {pe}"
        print("🚨 MySQL Error:", error_message)
        attempt += 1
    except Exception as e:
        error_message = str(e)
        print("🚨 Unexpected Error:", error_message)
        attempt += 1

# Step 5: Summarize or report failure
if data:
    print("\n--- Final Result ---")
    summary_messages = [
        {"role": "system", "content": "You are a helpful assistant that summarizes database query results."},
        {"role": "user", "content": f"Here are the results of the query:\n{data}\nSummarize this nicely for the user."}
    ]

    try:
        summary_response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=summary_messages,
            max_tokens=200
        )
        summary = summary_response.choices[0].message.content.strip()
        print("📄 Summary:\n", summary)
    except Exception as e:
        print(f"Failed to generate summary: {e}")
        print("Raw Data:", data)
else:
    print("\n❌ Failed after retries. Please rephrase your question or check the database/schema.")

# Close the database connection
if 'conn' in locals() and conn:
    conn.close()
    print("Database connection closed.")