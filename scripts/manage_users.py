import argparse
import sys
import os

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Firebase config first to ensure initialization
from auth.firebase_config import get_firebase_config
from auth.user_management import (
    create_user,
    list_users,
    delete_user,
    update_user,
    list_pending_users,
    approve_user,
    reject_user,
    delete_request_by_email,
    set_user_claims,
    reset_user_password
)

def main():
    parser = argparse.ArgumentParser(description='Manage Firebase users')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Create user command
    create_parser = subparsers.add_parser('create', help='Create a new user')
    create_parser.add_argument('email', help='User email (must end with @addisenergy.com)')
    create_parser.add_argument('password', help='User password')
    create_parser.add_argument('--display-name', help='User display name (optional)')

    # List users command
    subparsers.add_parser('list', help='List all users')

    # Delete user command
    delete_parser = subparsers.add_parser('delete', help='Delete a user')
    delete_parser.add_argument('uid', help='User UID')

    # Update user command
    update_parser = subparsers.add_parser('update', help='Update a user')
    update_parser.add_argument('uid', help='User UID')
    update_parser.add_argument('--email', help='New email (must end with @addisenergy.com)')
    update_parser.add_argument('--display-name', help='New display name')

    # Pending users commands
    pending_parser = subparsers.add_parser('pending', help='List pending user requests')
    
    approve_parser = subparsers.add_parser('approve', help='Approve a pending user request')
    approve_parser.add_argument('request_id', help='Request ID')
    
    reject_parser = subparsers.add_parser('reject', help='Reject a pending user request')
    reject_parser.add_argument('request_id', help='Request ID')
    reject_parser.add_argument('--reason', help='Rejection reason')

    # Delete request by email command
    delete_request_parser = subparsers.add_parser('delete-request', help='Delete any existing requests for an email')
    delete_request_parser.add_argument('email', help='Email address to delete requests for')

    # Set claims command
    set_claims_parser = subparsers.add_parser('set-claims', help='Set custom claims for an existing user')
    set_claims_parser.add_argument('uid', help='User UID')
    set_claims_parser.add_argument('--role', default='user', help='User role (default: user)')

    # Reset password command
    reset_password_parser = subparsers.add_parser('reset-password', help='Generate a password reset link for a user')
    reset_password_parser.add_argument('email', help='User email')

    args = parser.parse_args()

    try:
        if args.command == 'create':
            user = create_user(args.email, args.password, args.display_name)
            print(f"Created user: {user['email']} (UID: {user['uid']})")
        
        elif args.command == 'list':
            users = list_users()
            print("\nUsers:")
            for user in users:
                print(f"- {user['email']} (UID: {user['uid']})")
                print(f"  Display Name: {user['display_name']}")
                print(f"  Created: {user['created_at']}")
                print(f"  Disabled: {user['disabled']}\n")
        
        elif args.command == 'delete':
            if delete_user(args.uid):
                print(f"Deleted user with UID: {args.uid}")
        
        elif args.command == 'update':
            user = update_user(args.uid, args.display_name, args.email)
            print(f"Updated user: {user['email']} (UID: {user['uid']})")
        
        elif args.command == 'pending':
            pending = list_pending_users()
            print("\nPending Requests:")
            for request in pending:
                print(f"- Request ID: {request['id']}")
                print(f"  Email: {request['email']}")
                print(f"  Display Name: {request['display_name']}")
                print(f"  Role: {request['role']}")
                print(f"  Created: {request['created_at']}\n")
        
        elif args.command == 'approve':
            user = approve_user(args.request_id)
            print(f"Approved user: {user['email']} (UID: {user['uid']})")
        
        elif args.command == 'reject':
            if reject_user(args.request_id, args.reason):
                print(f"Rejected request: {args.request_id}")
        
        elif args.command == 'delete-request':
            if delete_request_by_email(args.email):
                print(f"Deleted all requests for email: {args.email}")
            else:
                print(f"No requests found for email: {args.email}")
        
        elif args.command == 'set-claims':
            user = set_user_claims(args.uid, args.role)
            print(f"Set claims for user: {user['email']} (UID: {user['uid']})")
            print(f"Custom claims: {user['custom_claims']}")
        
        elif args.command == 'reset-password':
            link = reset_user_password(args.email)
            print(f"Password reset link for {args.email}:")
            print(link)
        
        else:
            parser.print_help()

    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

if __name__ == '__main__':
    main() 