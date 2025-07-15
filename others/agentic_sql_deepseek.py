import pymysql
import re
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ------------------------
# 🔍 Database Functions
# ------------------------
def get_db_schema(cursor):
    """Get database schema as formatted string"""
    schema = ""
    cursor.execute("SHOW TABLES")
    try:
        tables = [row["Tables_in_" + os.getenv('MYSQL_DATABASE', 'SchoolDb')] for row in cursor.fetchall()]
    except KeyError:
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        columns = cursor.fetchall()
        schema += f"Table: {table}\n"
        for column in columns:
            if isinstance(column, dict):
                column_name = column["Field"]
                data_type = column["Type"]
            else:
                column_name = column[0]
                data_type = column[1]
            schema += f"- {column_name} ({data_type})\n"
        schema += "\n"
    return schema.strip()

# ------------------------
# 🧼 SQL Validation
# ------------------------
def extract_valid_sql(text):
    """
    Extracts and validates SQL from LLM response
    Returns: Valid SQL string
    Raises: ValueError if invalid
    """
    match = re.search(r"(SELECT\s.+?;)", text, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("No valid SELECT statement found in response")
    
    sql = match.group(1).strip()
    
    # MySQL-specific validation
    if "TOP" in sql.upper():
        raise ValueError("Use LIMIT instead of TOP for MySQL")
    
    return sql

# ------------------------
# 🤖 DeepSeek API
# ------------------------
def call_deepseek_api(prompt: str, api_key: str, model: str = "deepseek-chat"):
    """Call DeepSeek API and return response"""
    url = "https://api.deepseek.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 200
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# ------------------------
# 🧠 Prompt Engineering
# ------------------------
def build_prompt(user_question, schema):
    """Construct prompt for SQL generation"""
    return f"""
You are a SQL expert. Generate a MySQL SELECT query that answers this question:

Database Schema:
{schema}

Question: "{user_question}"

Rules:
1. Use ONLY the tables/columns shown above
2. Return ONLY the SQL query ending with ;
3. Use backticks for identifiers if needed
4. Use LIMIT not TOP
5. Never include explanations

SQL Query:
"""

# ------------------------
# 🚀 Main Execution
# ------------------------
def main():
    # Database connection
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
        print("✅ MySQL connection successful")
    except Exception as ex:
        print(f"❌ MySQL connection failed: {ex}")
        return

    # Initialize DeepSeek
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    if not DEEPSEEK_API_KEY:
        raise ValueError("Missing DEEPSEEK_API_KEY in .env")

    # User question
    user_question = "Find the names of all students who have a score higher than 150."
    print(f"\nQuestion: {user_question}")

    # Get schema
    schema = get_db_schema(cursor)
    
    # Generate and execute SQL
    try:
        prompt = build_prompt(user_question, schema)
        print("\nGenerating SQL...")
        raw_response = call_deepseek_api(prompt, DEEPSEEK_API_KEY)
        
        sql_query = extract_valid_sql(raw_response)  # Now properly defined
        print(f"Generated SQL:\n{sql_query}")

        cursor.execute(sql_query)
        results = cursor.fetchall()
        
        if results:
            print("\nResults:")
            for row in results:
                print(row)
        else:
            print("No results found")

    except ValueError as ve:
        print(f"SQL Validation Error: {ve}")
    except requests.exceptions.RequestException as re:
        print(f"API Error: {re}")
    except Exception as e:
        print(f"Unexpected Error: {e}")
    finally:
        conn.close()
        print("\nDatabase connection closed")

if __name__ == "__main__":
    main()