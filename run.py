#!/usr/bin/env python3
"""Entry point: python run.py [--dry-run]"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Run the AI & Science daily digest")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and score stories but do not send email",
    )
    args = parser.parse_args()

    try:
        from digest.digest import run
        run(dry_run=args.dry_run)
    except KeyError as e:
        print(f"Missing environment variable: {e}")
        print("Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
