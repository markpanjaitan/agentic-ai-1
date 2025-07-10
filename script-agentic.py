import pymysql  # Changed from pyodbc to pymysql for MySQL
import re
import os
from dotenv import load_dotenv
import anthropic

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
    tables = [row[0] for row in cursor.fetchall()]

    # For each table, fetch its columns and their data types
    for table in tables:
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        columns = cursor.fetchall()
        schema += f"Table: {table}\n"
        for column in columns:
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
    system_message_content = """
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
    
    messages = [
        {"role": "user", "content": user_message_content}
    ]
    
    return messages

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

# Step 0: Connect to MySQL (updated connection parameters)
try:
    conn = pymysql.connect(
        host='localhost',
        port=3306,
        user='markvp',
        password='12345',
        database='SchoolDb',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()
    print("MySQL database connection successful.")
except pymysql.Error as ex:
    print(f"MySQL connection failed: {ex}")
    print("Please ensure MySQL is running, the database exists, and credentials are correct.")
    exit()

# Step 1: Initialize Anthropic client
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found. Please set it in your .env file.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
ANTHROPIC_MODEL = "claude-3-opus-20240229" 
print(f"Anthropic client initialized with model: {ANTHROPIC_MODEL}")

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
    prompt_messages = build_prompt(user_question, schema, error_message, sql_query)
    
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=200,
            messages=prompt_messages
        )
        raw_response = response.content[0].text.strip()
        print(f"🔍 LLM Raw Response:\n{raw_response}")

        sql_query = extract_valid_sql(raw_response)
        print("✅ Extracted SQL:\n", sql_query)

        # Execute the SQL query
        cursor.execute(sql_query)
        data = cursor.fetchall()  # Using DictCursor so we get dictionaries directly

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
    except anthropic.APIError as ae:
        error_message = f"Anthropic API Error: {ae}"
        print("🚨 Anthropic API Error:", error_message)
        attempt += 1
    except Exception as e:
        error_message = str(e)
        print("🚨 Unexpected Error:", error_message)
        attempt += 1

# Step 5: Summarize or report failure
if data:
    print("\n--- Final Result ---")
    summary_user_message = f"""
Here are the results of the query:\n{data}
Summarize this nicely for the user.
"""
    summary_messages = [{"role": "user", "content": summary_user_message}]

    try:
        summary_response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=200,
            messages=summary_messages
        )
        summary = summary_response.content[0].text.strip()
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