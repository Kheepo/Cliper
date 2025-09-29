#!/usr/bin/env python3

from api.utils.supabase_client import get_supabase_admin_client

def main():
    supabase = get_supabase_admin_client()
    result = supabase.table('jobs').select('id, title, status').limit(5).execute()
    print('Available video jobs:')
    for job in result.data:
        print(f'  ID: {job["id"]}, Title: {job.get("title", "N/A")}, Status: {job["status"]}')

if __name__ == "__main__":
    main()