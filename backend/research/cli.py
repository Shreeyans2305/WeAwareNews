"""Operator-only pilot administration and worker entry point.

Run from backend: python -m research.cli --help. No email or payment integration.
"""
import argparse
import json
import logging
import os
import re
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from .store import Store, ResearchError, transaction, decoded


@contextmanager
def database():
    import psycopg2
    password = os.getenv('DB_PASS')
    if not password:
        from google.cloud import secretmanager
        project = os.environ['GOOGLE_CLOUD_PROJECT']
        response = secretmanager.SecretManagerServiceClient().access_secret_version(
            request={'name': 'projects/%s/secrets/db-password/versions/latest' % project})
        password = response.payload.data.decode()
    connection = psycopg2.connect(host=os.environ['DB_HOST'], port=int(os.getenv('DB_PORT', '5432')),
                                  dbname=os.getenv('DB_NAME', 'weaware'), user=os.getenv('DB_USER', 'weaware_user'),
                                  password=password, connect_timeout=10, application_name='sherlock-pilot')
    try:
        yield connection
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description='Journalist Jeff private research pilot')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('migrate')
    grant = commands.add_parser('grant', help='Set a tester allowance; granting is not an automatic monthly top-up')
    grant.add_argument('--uid', required=True)
    grant.add_argument('--credits', type=int, default=3, choices=range(1, 21))
    grant.add_argument('--days', type=int, default=30, choices=range(1, 91))
    grant.add_argument('--actor', required=True)
    email_grant = commands.add_parser('grant-email', help='Invite a specific verified email; activates at first sign-in without sending mail')
    email_grant.add_argument('--email', required=True)
    email_grant.add_argument('--credits', type=int, default=3, choices=range(1,21))
    email_grant.add_argument('--days', type=int, default=30, choices=range(1,91))
    email_grant.add_argument('--actor', required=True)
    revoke = commands.add_parser('revoke')
    revoke.add_argument('--uid', required=True)
    revoke.add_argument('--actor', required=True)
    budget = commands.add_parser('budget', help='Inspect budget or pause/enable within the immutable $10 pilot ceiling')
    budget.add_argument('--enable', action='store_true')
    budget.add_argument('--pause', action='store_true')
    budget.add_argument('--actor')
    commands.add_parser('run-once', help='Recover expired work and process at most one request')
    commands.add_parser('review-list')
    inspect = commands.add_parser('inspect', help='Private evidence, draft and verification output for human review')
    inspect.add_argument('id')
    decision = commands.add_parser('review')
    decision.add_argument('id')
    decision.add_argument('--decision', choices=['approve', 'reject'], required=True)
    decision.add_argument('--actor', required=True)
    decision.add_argument('--note', required=True, help='Document source checks and decision')
    preview = commands.add_parser('preview-pdf', help='Private, clearly marked unapproved editor copy; never publishes a report')
    preview.add_argument('id')
    preview.add_argument('--output', required=True)
    commands.add_parser('purge-evidence', help='Delete raw artifacts older than 30 days; preserve usage records')
    args = parser.parse_args()
    with database() as db:
        store = Store(db)
        if args.command == 'migrate':
            with transaction(db) as cur:
                for migration in sorted(Path(__file__).with_name('migrations').glob('*.sql')):
                    cur.execute(migration.read_text())
            print('Sherlock schema ready; budget remains disabled on first migration.')
        elif args.command == 'grant-email':
            email = args.email.strip().lower()
            if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
                parser.error('Supply a valid email address.')
            with transaction(db) as cur:
                cur.execute('SELECT redeemed_uid FROM sherlock_invites WHERE email=%s FOR UPDATE', (email,))
                row = cur.fetchone()
                if row and row[0]:
                    parser.error('Invitation already activated; use the UID-based grant command for changes.')
                cur.execute("INSERT INTO sherlock_invites(email,expires_at,credits,granted_by) VALUES (%s,NOW()+%s*INTERVAL '1 day',%s,%s) ON CONFLICT(email) DO UPDATE SET expires_at=EXCLUDED.expires_at,credits=EXCLUDED.credits,granted_by=EXCLUDED.granted_by", (email,args.days,args.credits,args.actor))
                cur.execute("INSERT INTO sherlock_audit(actor,action,target,note) VALUES (%s,'grant_email',%s,%s)", (args.actor,email,'Manual invitation; no email sent'))
            print('Manual invitation saved; verified sign-in activates it. No email sent.')
        elif args.command in ('grant', 'revoke'):
            with transaction(db) as cur:
                if args.command == 'grant':
                    cur.execute('SELECT uid FROM sherlock_access WHERE uid=%s FOR UPDATE', (args.uid,))
                    cur.execute('SELECT 1 FROM sherlock_requests WHERE uid=%s AND status IN (\'queued\',\'researching\',\'awaiting_review\')', (args.uid,))
                    if cur.fetchone():
                        parser.error('Wait for active work before resetting this tester allowance.')
                    cur.execute("INSERT INTO sherlock_access(uid,expires_at,credits,granted_by) VALUES (%s,NOW()+%s*INTERVAL '1 day',%s,%s) ON CONFLICT(uid) DO UPDATE SET expires_at=EXCLUDED.expires_at,credits=EXCLUDED.credits,granted_by=EXCLUDED.granted_by,updated_at=NOW()", (args.uid, args.days, args.credits, args.actor))
                else:
                    cur.execute('UPDATE sherlock_access SET expires_at=NOW(),updated_at=NOW() WHERE uid=%s', (args.uid,))
                cur.execute('INSERT INTO sherlock_audit(actor,action,target,note) VALUES (%s,%s,%s,%s)', (args.actor, args.command, args.uid, 'Manual tester access'))
            print('Tester access updated.')
        elif args.command == 'budget':
            if args.enable or args.pause:
                if not args.actor or (args.enable and args.pause):
                    parser.error('Choose one budget action and supply --actor.')
                with transaction(db) as cur:
                    cur.execute('UPDATE sherlock_budget SET enabled=%s WHERE id=1', (args.enable,))
                    cur.execute('INSERT INTO sherlock_audit(actor,action,target,note) VALUES (%s,%s,%s,%s)', (args.actor, 'budget', 'pilot', 'enabled' if args.enable else 'paused'))
            with transaction(db) as cur:
                cur.execute('SELECT enabled,ceiling,committed FROM sherlock_budget WHERE id=1')
                print(json.dumps(cur.fetchone(), default=str))
        elif args.command == 'run-once':
            store.expire()
            store.purge_artifacts()
            # Preflight before claiming so bad configuration does not consume a
            # tester request. Provider creation performs no paid API calls.
            from .providers import Providers
            Providers(store, {})
            job = store.claim()
            if not job:
                print('No eligible queued work, or pilot paused.')
                return
            try:
                from .pipeline import investigate
                report, review = investigate(store, job, Providers(store, job))
                # Finalize through a fresh connection after long provider calls.
                # This retries no paid operation and still requires the lease.
                with database() as completion_db:
                    Store(completion_db).finish(job, report, review)
                print('Investigation ready for private editor review: ' + job['id'])
            except Exception as exc:
                # Provider diagnostics stay in the private expiring artifact store;
                # logs retain only the status code and exception class.
                if isinstance(exc, urllib.error.HTTPError):
                    try:
                        with database() as diagnostic_db:
                            Store(diagnostic_db).artifact(job, 'provider-error', {'httpStatus': exc.code, 'response': exc.read(4000).decode('utf-8', errors='replace')})
                    except Exception:
                        logging.warning('Private provider diagnostic unavailable for %s', job['id'])
                code = exc.code if isinstance(exc, ResearchError) else ('provider_http_%s' % exc.code if isinstance(exc, urllib.error.HTTPError) else 'research_failed')
                # Never log questions, source bodies, provider payloads or secrets.
                logging.error('Sherlock request %s failed (%s, %s)', job['id'], code, type(exc).__name__)
                with database() as completion_db:
                    Store(completion_db).finish(job, error=code)
        elif args.command == 'review-list':
            with transaction(db) as cur:
                cur.execute("SELECT id,question,created_at,committed,report_length FROM sherlock_requests WHERE status='awaiting_review' ORDER BY created_at")
                print(json.dumps(cur.fetchall(), default=str, indent=2))
        elif args.command == 'inspect':
            with transaction(db) as cur:
                cur.execute('SELECT question,scope,status,report,review,committed,report_length FROM sherlock_requests WHERE id=%s', (args.id,))
                print(json.dumps(cur.fetchone(), default=str, indent=2))
                cur.execute('SELECT name,data FROM sherlock_artifacts WHERE request_id=%s ORDER BY created_at', (args.id,))
                print(json.dumps(cur.fetchall(), default=str, indent=2))
        elif args.command == 'preview-pdf':
            with transaction(db) as cur:
                cur.execute('SELECT uid FROM sherlock_requests WHERE id=%s', (args.id,))
                row = cur.fetchone()
            if not row:
                parser.error('Investigation not found.')
            investigation = store.detail(row[0], args.id)
            # Reader APIs hide drafts; privileged CLI reads the pending draft.
            with transaction(db) as cur:
                cur.execute('SELECT report FROM sherlock_requests WHERE id=%s', (args.id,))
                investigation['report'] = decoded(cur.fetchone()[0])
            from .pdf import render_report_pdf
            content = render_report_pdf(investigation, editor_preview=True)
            output = Path(args.output)
            if output.exists():
                parser.error('Choose a new output path; previews never overwrite an existing file.')
            output.write_bytes(content)
            print('Private, unapproved editor PDF created: ' + str(output.resolve()))
        elif args.command == 'review':
            if len(args.note.strip()) < 20:
                parser.error('Record a meaningful review note of at least 20 characters.')
            with transaction(db) as cur:
                cur.execute('SELECT uid FROM sherlock_access WHERE uid=(SELECT uid FROM sherlock_requests WHERE id=%s) FOR UPDATE', (args.id,))
                cur.execute("SELECT report,review FROM sherlock_requests WHERE id=%s AND status='awaiting_review' FOR UPDATE", (args.id,))
                row = cur.fetchone()
                if not row:
                    parser.error('Investigation is not awaiting review.')
                if args.decision == 'approve':
                    report, review = decoded(row[0]), decoded(row[1])
                    if not report or not review or review.get('approved') is not True:
                        parser.error('Automated verification must pass before approval.')
                    cur.execute("UPDATE sherlock_requests SET status='completed',stage='completed',credit_state='consumed',completed_at=NOW(),reviewed_by=%s,review_note=%s WHERE id=%s", (args.actor, args.note, args.id))
                else:
                    cur.execute("UPDATE sherlock_requests SET status='failed',stage='failed',error_code='editor_rejected',reviewed_by=%s,review_note=%s WHERE id=%s", (args.actor, args.note, args.id))
                    store._refund(cur, args.id)
                cur.execute('INSERT INTO sherlock_audit(actor,action,target,note) VALUES (%s,%s,%s,%s)', (args.actor, args.decision, args.id, args.note))
            print('Review recorded; website report visibility updated.')
        elif args.command == 'purge-evidence':
            print('Expired artifacts deleted: %s' % store.purge_artifacts())


if __name__ == '__main__':
    main()
