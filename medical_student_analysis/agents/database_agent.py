import pymysql
import re
import os
import google.generativeai as genai

class DatabaseAgent:
    def __init__(self, db_config, gemini_model_name="gemini-1.5-flash"):
        self.db_config = db_config
        self.model = genai.GenerativeModel(gemini_model_name)
        self.conn = None
        self.cursor = None

    def connect(self):
        try:
            self.conn = pymysql.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database=self.db_config['database'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.conn.cursor()
            print("DatabaseAgent: MySQL database connection successful.")
            return True
        except pymysql.Error as ex:
            print(f"DatabaseAgent: MySQL connection failed: {ex}")
            return False

    def disconnect(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("DatabaseAgent: Database connection closed.")

    def get_schema(self):
        """Introspects the MySQL database to retrieve schema information."""
        if not self.cursor:
            print("DatabaseAgent: Not connected to database. Cannot get schema.")
            return None
        
        schema = ""
        self.cursor.execute("SHOW TABLES")
        
        tables = []
        fetched_tables = self.cursor.fetchall()
        
        if fetched_tables:
            db_name = self.db_config.get('database', 'SchoolDb')
            
            # --- DEBUGGING: Print the first row to see its structure ---
            print(f"DatabaseAgent: Debugging fetched_tables[0]: {fetched_tables[0]}")
            # --- END DEBUGGING ---

            if isinstance(fetched_tables[0], dict):
                # Attempt to find the correct key for the table name
                table_key = None
                for key in fetched_tables[0]:
                    if key.lower().startswith('tables_in_') or key.lower() == 'table':
                        table_key = key
                        break
                
                if table_key:
                    tables = [row[table_key] for row in fetched_tables]
                else:
                    print("DatabaseAgent: Warning: Could not determine the table name key from dictionary. Available keys:", fetched_tables[0].keys())
                    return None
            else: # Assume it's a list of tuples
                tables = [row[0] for row in fetched_tables]

        if not tables:
            print("DatabaseAgent: No tables found or failed to extract table names.")
            return None

        for table in tables:
            self.cursor.execute(f"SHOW COLUMNS FROM `{table}`")
            columns = self.cursor.fetchall()
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

    def _build_sql_prompt(self, user_question, schema, error_message=None, previous_sql=None):
        """Constructs the prompt messages for the LLM to generate SQL."""
        system_instruction = """
You are a SQL expert. You will receive a database schema and a user question.
Your task is to generate a valid MySQL SELECT query that answers the user's question.

You MUST adhere to these rules:
- Use ONLY table and column names exactly as provided in the schema.
- NEVER invent or singularize table names.
- Output ONLY a valid MySQL SELECT statement, ending with a semicolon.
- Do NOT include any explanations, comments, or additional text outside of the SQL query.
- Use backticks (`) for quoting identifiers if needed.
- Use LIMIT instead of TOP for row limiting.

IMPORTANT SEMANTIC INSTRUCTIONS:
- If the user's question refers to or implies specific 'students' (e.g., 'best student', 'top performer', 'healthiest student'), you MUST include their `first_name` and `last_name` from the `Students` table in your SELECT clause.
- Ensure you join all necessary tables (e.g., `Students`, `Enrollments`, `Courses`) to retrieve all information relevant to the question.
- Always aim to provide complete data that allows identification of individuals mentioned in the question.
"""

        user_message_content = f"""
Schema:
{schema}

Question: "{user_question}"
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
        user_message_content += "\nOutput:"
        
        contents = [
            {"role": "user", "parts": [{"text": system_instruction + "\n\n" + user_message_content}]}
        ]
        return contents

    def _extract_valid_sql(self, text):
        """Extracts a valid SQL SELECT statement from the LLM's response."""
        match = re.search(r"(SELECT\s.+?;)", text, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError("No valid SELECT statement found in LLM response.")
        sql = match.group(1).strip()
        
        if "TOP" in sql.upper():
            raise ValueError("Invalid keyword 'TOP' for MySQL. Use LIMIT instead.")
        
        return sql

    def query_database(self, user_question, schema, max_retries=2):
        """Generates SQL and executes it, with retry logic."""
        attempt = 0
        error_message = None
        sql_query = None

        while attempt < max_retries:
            print(f"DatabaseAgent: Attempt {attempt + 1} to generate and execute SQL for: '{user_question}'")
            prompt_contents = self._build_sql_prompt(user_question, schema, error_message, sql_query)
            
            try:
                response = self.model.generate_content(
                    prompt_contents,
                    generation_config={"max_output_tokens": 200}
                )
                
                raw_response = response.text.strip()
                print(f"DatabaseAgent: 🔍 LLM Raw Response:\n{raw_response}")

                sql_query = self._extract_valid_sql(raw_response)
                print(f"DatabaseAgent: ✅ Extracted SQL:\n{sql_query}")

                self.cursor.execute(sql_query)
                data = self.cursor.fetchall()
                print("DatabaseAgent: SQL query executed successfully.")
                return data

            except ValueError as ve:
                error_message = str(ve)
                print(f"DatabaseAgent: 🚨 Validation Error: {error_message}")
                attempt += 1
            except pymysql.Error as pe:
                error_message = f"MySQL Error: {pe}"
                print(f"DatabaseAgent: 🚨 MySQL Error: {error_message}")
                attempt += 1
            except Exception as e:
                error_message = str(e)
                print(f"DatabaseAgent: 🚨 Unexpected Error during SQL generation/execution: {error_message}")
                attempt += 1
        
        print("DatabaseAgent: ❌ Failed to generate and execute a successful SQL query after retries.")
        return None