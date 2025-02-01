from secrets import token_hex

# Generate a 32-byte (256-bit) random key
secret_key = token_hex(32)
print(f"SECRET_KEY={secret_key}") 