# Restaurant Management System

A team project designed to simplify and automate the core operations of a restaurant using a web-based management system.

## Table of Contents

- [Features](#features)
- [Technologies Used](#technologies-used)
- [Installation](#installation)
- [Usage](#usage)
- [Database Schema](#database-schema)
- [Contact](#contact)

## Features

- **Order Management**: Manage customer orders from placement to completion.
- **Billing System**: Automatically generate bills based on orders.
- **Menu Management**: Add, update, and delete menu items.
- **Staff Management**: Handle staff details and responsibilities.

## Technologies Used

- **Backend**: Python (Flask)
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQL (via `schema.sql`)
- **Version Control**: Git & GitHub

## Installation

To run the project locally:

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/Pradeepaa001/RestaurantManagementSystem.git
   cd RestaurantManagementSystem

2. **Set Up a Virtual Environment** *(Optional but recommended)*:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
   ```

3. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:

   In the project root directory (same level as `app.py`), create a `.env` file and add the following:

   ```env
   DB_HOST=localhost
   DB_USER=YOUR_USER_NAME
   DB_PASSWORD=YOUR_PASSWD
   DB_NAME=restaurant_db
   ```

   Replace `YOUR_USER_NAME` and `YOUR_PASSWD` with your actual SQL credentials.

5. **Set Up the Database**:

   Run the `schema.sql` file in your SQL database (e.g., MySQL/PostgreSQL):

   ```sql
   -- Example for MySQL
   source path/to/schema.sql;
   ```

## Usage

To start the application:

```bash
python app.py
```

> `flask run` may work if environment variables are configured properly, but `python app.py` is the recommended method for this project.

## Database Schema

All tables and relationships are defined in the `schema.sql` file. Make sure to execute it in your SQL database before running the app.
