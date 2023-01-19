"""
Insert data into database
"""
from db_control import DatabaseControl

if __name__ == "__main__":
    db_control = DatabaseControl()
    db_control.list_tables()
    db_control.list_table_values(table_name="harmony")
