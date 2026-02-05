# Sample Data Files

This directory contains sample data files for testing upload scripts.

## Files

- `users.json` - Sample user data
- `products.json` - Sample product data

## Usage

### Upload users:
```bash
python scripts/upload_db_data.py insert-json --file data/sample_documents/users.json --table users
```

### Upload products:
```bash
python scripts/upload_db_data.py insert-json --file data/sample_documents/products.json --table products
```

## File Format

### Users JSON:
```json
[
  {
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
  }
]
```

### Products JSON:
```json
[
  {
    "name": "Product Name",
    "description": "Product description",
    "price": 99.99,
    "category": "Category",
    "stock": 10
  }
]
```
