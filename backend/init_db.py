"""
Database initialization script
Run this once to create the MySQL database and tables
"""

import mysql.connector
from mysql.connector import Error

# MySQL connection credentials
HOST = "localhost"
USER = "root"
PASSWORD = ""  # No password

def create_database():
    """Create the database and tables"""
    try:
        # Connect to MySQL server (without selecting a database)
        connection = mysql.connector.connect(
            host=HOST,
            user=USER,
            password=PASSWORD
        )
        cursor = connection.cursor()

        # Create database
        print("Creating database 'smartchat_db'...")
        cursor.execute("CREATE DATABASE IF NOT EXISTS smartchat_db")
        cursor.execute("USE smartchat_db")

        # Create subscribers table
        print("Creating 'subscribers' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            plan ENUM('free', 'pro', 'enterprise') DEFAULT 'free',
            status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)

        # Create chatbots table
        print("Creating 'chatbots' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatbots (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subscriber_id INT NOT NULL,
            name VARCHAR(150) NOT NULL,
            status ENUM('active', 'inactive', 'training') DEFAULT 'inactive',
            conversations INT DEFAULT 0,
            accuracy DECIMAL(5,2) DEFAULT 0.00,
            response_time DECIMAL(5,2) DEFAULT 0.00,
            success_rate DECIMAL(5,2) DEFAULT 0.00,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subscriber_id) REFERENCES subscribers(id) ON DELETE CASCADE
        )
        """)

        # Create chatbot_usage_stats table
        print("Creating 'chatbot_usage_stats' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_usage_stats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            chatbot_id INT NOT NULL,
            date DATE NOT NULL,
            messages_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chatbot_id) REFERENCES chatbots(id) ON DELETE CASCADE
        )
        """)

        connection.commit()
        print("✓ Database and tables created successfully!")

        cursor.close()
        connection.close()

    except Error as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    create_database()
