#!/usr/bin/env python3
"""
Fix all endpoints in chatbots.py to accept token from Authorization header.
"""
import re

# Read the file
with open(r'backend/routers/chatbots.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern 1: Replace "token: str = Query(...)" in function signatures
# We need to replace the entire parameter and move it after db: Session
content = re.sub(
    r',\s*token: str = Query\(\.\.\.\),\s*db: Session = Depends\(get_db\)',
    ',\n    db: Session = Depends(get_db),\n    authorization: Optional[str] = None',
    content
)

# Pattern 2: Handle cases where token is the last parameter before db
content = re.sub(
    r'token: str = Query\(\.\.\.\),\s*db: Session = Depends\(get_db\)',
    'db: Session = Depends(get_db),\n    authorization: Optional[str] = None',
    content
)

# Pattern 3: Replace the first occurrence of token extraction within function bodies
# Look for patterns like: user = get_user_from_token(token, db)
# And replace with: token = extract_token_from_header(authorization) \n    user = get_user_from_token(token, db)

# Find all function definitions with parameters
functions_to_fix = re.finditer(
    r'def\s+\w+\([^)]*authorization: Optional\[str\] = None\s*\):.*?(?=\n\n@|\ndef\s|\Z)',
    content,
    re.DOTALL
)

for func_match in functions_to_fix:
    func_text = func_match.group(0)
    
    # Check if this function already has token extraction
    if 'token = extract_token_from_header' not in func_text:
        # Find the first get_user_from_token call or the first line after the function def
        if 'get_user_from_token' in func_text:
            # Insert token extraction before first get_user_from_token call
            new_func = re.sub(
                r'(\n\s+)(user = get_user_from_token)',
                r'\1token = extract_token_from_header(authorization)\n\1\2',
                func_text,
                count=1
            )
        elif 'verify_chatbot_owner' in func_text and 'user = ' not in func_text:
            # Insert before verify_chatbot_owner if there's no user = line
            new_func = re.sub(
                r'(\n\s+)(verify_chatbot_owner)',
                r'\1token = extract_token_from_header(authorization)\n\1\2',
                func_text,
                count=1
            )
        elif '"""' in func_text:  # Has a docstring
            # Insert after the docstring
            new_func = re.sub(
                r'("""\).*?\n)(\s+)',
                r'\1\2token = extract_token_from_header(authorization)\n\2',
                func_text,
                count=1
            )
        else:
            # Insert at the beginning of the function body (after the : line)
            new_func = re.sub(
                r'(\):\n)(\s+)',
                r'\1\2token = extract_token_from_header(authorization)\n\2',
                func_text,
                count=1
            )
        
        content = content.replace(func_text, new_func)

# Write back
with open(r'backend/routers/chatbots.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Fixed all token parameter patterns in chatbots.py")
