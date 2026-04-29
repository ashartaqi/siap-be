# SIAP-BE

A FastAPI backend application with PostgreSQL database.

## Prerequisites

Before running this application, ensure you have the following installed:

- **Python**: 3.12.12
- **PostgreSQL**: 16

## Setup

### 1. Create a virtual environment

```bash
python3 -m venv .venv
```

### 2. Install dependencies

```bash
make install
```

### 3. Set up environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

### 4. Create the database

Open PostgreSQL and create a new database that matches the `POSTGRES_DB_NAME` you set in your `.env` file:

```bash
psql -U postgres
```

```sql
CREATE DATABASE your_db_name;
\q
```

Make sure the `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` values in your `.env` match your local PostgreSQL setup.

### 5. Run the application

Start the development server:

```bash
make dev
```

The API should now be running locally.

## API Testing

A Postman collection is included at the end of this repository to help you test the available endpoints. Import the collection into Postman to get started.