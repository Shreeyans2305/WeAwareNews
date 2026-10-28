"""Database transactions shared by the API and off-request worker.

All money is Decimal. Reserved/ambiguous provider calls remain charged at their
upper bound. No automatic provider retries; restarting cannot repeat a call.
"""
import json
import uuid
from contextlib import contextmanager
from decimal import Decimal, ROUND_CEILING
from .lengths import length_settings

ACTIVE = ('queued', 'researching', 'awaiting_review')


class ResearchError(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def money(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid amount')
    return result.quantize(Decimal('0.00000001'), rounding=ROUND_CEILING)


@contextmanager
def transaction(db):
    cur = db.cursor()
    try:
        yield cur
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


class Store:
    def __init__(self, db):
        self.db = db

    def redeem_invite(self, uid, verified_email):
        # Called only with email from a server-verified Firebase token. Never
        # accept an email or UID from request bodies or URL parameters.
        if not isinstance(verified_email, str) or not verified_email.strip():
            return
        with transaction(self.db) as cur:
            cur.execute('SELECT expires_at,credits,granted_by,redeemed_uid FROM sherlock_invites WHERE email=%s AND expires_at>NOW() FOR UPDATE', (verified_email.strip().lower(),))
            row = cur.fetchone()
            if not row or row[3]:
                return
            cur.execute('INSERT INTO sherlock_access(uid,expires_at,credits,granted_by) VALUES (%s,%s,%s,%s) ON CONFLICT(uid) DO NOTHING', (uid,row[0],row[1],row[2]))
            cur.execute('UPDATE sherlock_invites SET redeemed_uid=%s WHERE email=%s', (uid,verified_email.strip().lower()))
            cur.execute("INSERT INTO sherlock_audit(actor,action,target,note) VALUES (%s,'redeem_invite',%s,%s)", ('firebase-verified-account',uid,'Manual email invitation activated'))

    def access(self, uid):
        with transaction(self.db) as cur:
            cur.execute('SELECT credits, expires_at, expires_at > NOW() FROM sherlock_access WHERE uid=%s', (uid,))
            row = cur.fetchone()
            cur.execute('SELECT enabled, committed < ceiling FROM sherlock_budget WHERE id=1')
            budget = cur.fetchone()
        return {'eligible': bool(row and row[2]), 'credits': row[0] if row else 0,
                'expiresAt': row[1].isoformat() if row else None,
                'acceptingRequests': bool(budget and budget[0] and budget[1]),
                'creditPolicy': 'Pilot credits last until tester access expires. Technical failures return a credit.'}

    def submit(self, uid, question, scope, key, report_length='standard'):
        length_settings(report_length)
        with transaction(self.db) as cur:
            # Serialize submissions, cancellation and refunds for this owner.
            cur.execute('SELECT credits, expires_at > NOW() FROM sherlock_access WHERE uid=%s FOR UPDATE', (uid,))
            access = cur.fetchone()
            cur.execute('SELECT id, question, scope, report_length FROM sherlock_requests WHERE uid=%s AND submission_key=%s', (uid, key))
            previous = cur.fetchone()
            if previous:
                if tuple(previous[1:]) != (question, scope, report_length):
                    raise ResearchError('idempotency_conflict', 'This submission key belongs to a different question.')
                return previous[0]
            if not access or not access[1]:
                raise ResearchError('access_required', 'Sherlock Mode is an invite-only pilot. Ask for tester access.', 403)
            cur.execute('SELECT enabled, committed < ceiling FROM sherlock_budget WHERE id=1')
            budget = cur.fetchone()
            if not budget or not all(budget):
                raise ResearchError('paused', 'Research is paused while the pilot budget is checked.', 503)
            if access[0] <= 0:
                raise ResearchError('no_credits', 'You have no pilot research credits remaining.')
            cur.execute("SELECT 1 FROM sherlock_requests WHERE uid=%s AND status IN ('queued','researching','awaiting_review')", (uid,))
            if cur.fetchone():
                raise ResearchError('active_request', 'Please wait for your current investigation to finish.')
            request_id = str(uuid.uuid4())
            cur.execute("INSERT INTO sherlock_requests(id,uid,submission_key,question,scope,report_length,cost_limit) VALUES (%s,%s,%s,%s,%s,%s,0.5)",
                        (request_id, uid, key, question, scope, report_length))
            cur.execute('UPDATE sherlock_access SET credits=credits-1 WHERE uid=%s', (uid,))
        return request_id

    def listing(self, uid):
        with transaction(self.db) as cur:
            cur.execute('SELECT id,question,scope,status,stage,created_at,due_at,error_code,report_length FROM sherlock_requests WHERE uid=%s ORDER BY created_at DESC LIMIT 50', (uid,))
            rows = cur.fetchall()
        keys = ('id', 'question', 'scope', 'status', 'stage', 'createdAt', 'dueAt', 'errorCode', 'reportLength')
        return [dict(zip(keys, [v.isoformat() if hasattr(v, 'isoformat') else v for v in row])) for row in rows]

    def detail(self, uid, request_id):
        with transaction(self.db) as cur:
            cur.execute('SELECT id,question,scope,status,stage,created_at,due_at,error_code,report,completed_at,report_length FROM sherlock_requests WHERE uid=%s AND id=%s', (uid, request_id))
            row = cur.fetchone()
        if not row:
            raise ResearchError('not_found', 'Investigation not found.', 404)
        keys = ('id', 'question', 'scope', 'status', 'stage', 'createdAt', 'dueAt', 'errorCode', 'report', 'completedAt', 'reportLength')
        result = dict(zip(keys, [v.isoformat() if hasattr(v, 'isoformat') else v for v in row]))
        result['report'] = decoded(row[8]) if row[3] == 'completed' else None
        if result['report']:
            with transaction(self.db) as cur:
                cur.execute("SELECT data FROM sherlock_artifacts WHERE request_id=%s AND name LIKE 'google-search-%%' AND created_at>NOW()-INTERVAL '30 days' ORDER BY name", (request_id,))
                result['report']['searchDiscovery'] = [decoded(item[0]) for item in cur.fetchall()]
        return result

    def cancel(self, uid, request_id):
        with transaction(self.db) as cur:
            cur.execute('SELECT uid FROM sherlock_access WHERE uid=%s FOR UPDATE', (uid,))
            cur.execute('SELECT status FROM sherlock_requests WHERE uid=%s AND id=%s FOR UPDATE', (uid, request_id))
            row = cur.fetchone()
            if not row:
                raise ResearchError('not_found', 'Investigation not found.', 404)
            if row[0] == 'cancelled':
                return
            if row[0] != 'queued':
                raise ResearchError('already_started', 'Only queued investigations can be cancelled.')
            self._refund(cur, request_id)
            cur.execute("UPDATE sherlock_requests SET status='cancelled',stage='cancelled' WHERE id=%s", (request_id,))

    @staticmethod
    def _refund(cur, request_id):
        cur.execute("UPDATE sherlock_requests SET credit_state='refunded' WHERE id=%s AND credit_state='reserved' RETURNING uid", (request_id,))
        row = cur.fetchone()
        if row:
            cur.execute('UPDATE sherlock_access SET credits=LEAST(100,credits+1) WHERE uid=%s', (row[0],))

    def claim(self):
        with transaction(self.db) as cur:
            # All reserve paths take this global lock first, then a request lock.
            cur.execute('SELECT enabled, committed < ceiling FROM sherlock_budget WHERE id=1 FOR UPDATE')
            budget = cur.fetchone()
            if not budget or not all(budget):
                return None
            cur.execute("SELECT id,question,scope,report_length FROM sherlock_requests WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None
            token = str(uuid.uuid4())
            cur.execute("UPDATE sherlock_requests SET status='researching',stage='discovery',lease_token=%s,lease_until=NOW()+INTERVAL '30 minutes' WHERE id=%s", (token, row[0]))
        return {'id': row[0], 'question': row[1], 'scope': row[2], 'token': token, 'reportLength': row[3]}

    def reserve(self, job, name, amount):
        amount = money(amount)
        if amount <= 0:
            raise ValueError('Reservation must be positive')
        with transaction(self.db) as cur:
            cur.execute('SELECT enabled,ceiling,committed FROM sherlock_budget WHERE id=1 FOR UPDATE')
            budget = cur.fetchone()
            cur.execute("SELECT cost_limit,committed FROM sherlock_requests WHERE id=%s AND lease_token=%s AND status='researching' AND lease_until>NOW() FOR UPDATE", (job['id'], job['token']))
            request = cur.fetchone()
            if not request:
                raise ResearchError('lease_lost', 'Worker lease is no longer valid.')
            if not budget or not budget[0] or money(budget[2]) + amount > money(budget[1]) or money(request[1]) + amount > money(request[0]):
                raise ResearchError('budget_exhausted', 'Research spending limit reached.')
            cur.execute('SELECT 1 FROM sherlock_operations WHERE request_id=%s AND name=%s', (job['id'], name))
            if cur.fetchone():
                raise ResearchError('call_already_reserved', 'A previous attempt may already have been billed; manual review required.')
            cur.execute('INSERT INTO sherlock_operations(request_id,name,reserved) VALUES (%s,%s,%s)', (job['id'], name, amount))
            cur.execute('UPDATE sherlock_budget SET committed=committed+%s WHERE id=1', (amount,))
            cur.execute('UPDATE sherlock_requests SET committed=committed+%s,stage=%s WHERE id=%s', (amount, name, job['id']))
        return amount

    def settle(self, job, name, actual, metadata):
        actual = money(actual)
        with transaction(self.db) as cur:
            cur.execute('SELECT id FROM sherlock_budget WHERE id=1 FOR UPDATE')
            cur.execute('SELECT id FROM sherlock_requests WHERE id=%s FOR UPDATE', (job['id'],))
            cur.execute('SELECT reserved,state FROM sherlock_operations WHERE request_id=%s AND name=%s FOR UPDATE', (job['id'], name))
            row = cur.fetchone()
            if not row or row[1] != 'reserved':
                raise ResearchError('settlement_conflict', 'Operation cannot be settled twice.')
            reserved = money(row[0])
            if actual > reserved:
                # Keep the full reserve and shut down future spending. Requires an
                # operator to reconcile the provider bill before resuming.
                cur.execute('UPDATE sherlock_budget SET enabled=FALSE WHERE id=1')
                cur.execute('UPDATE sherlock_operations SET metadata=%s::jsonb WHERE request_id=%s AND name=%s', (json.dumps({'rateMismatch': True, 'reportedCost': str(actual)}), job['id'], name))
            else:
                release = reserved - actual
                cur.execute('UPDATE sherlock_budget SET committed=committed-%s WHERE id=1', (release,))
                cur.execute('UPDATE sherlock_requests SET committed=committed-%s WHERE id=%s', (release, job['id']))
                cur.execute("UPDATE sherlock_operations SET charged=%s,state='settled',metadata=%s::jsonb WHERE request_id=%s AND name=%s", (actual, json.dumps(metadata), job['id'], name))
        if actual > reserved:
            raise ResearchError('rate_mismatch', 'Provider usage exceeded the configured bound; pilot paused.')

    def artifact(self, job, name, data):
        with transaction(self.db) as cur:
            cur.execute("SELECT id FROM sherlock_requests WHERE id=%s AND lease_token=%s AND status='researching' AND lease_until>NOW() FOR UPDATE", (job['id'], job['token']))
            if not cur.fetchone():
                raise ResearchError('lease_lost', 'Worker lease is no longer valid.')
            cur.execute('INSERT INTO sherlock_artifacts(request_id,name,data) VALUES (%s,%s,%s::jsonb)', (job['id'], name, json.dumps(data)))

    def finish(self, job, report=None, review=None, error=None):
        with transaction(self.db) as cur:
            # Same owner-first locking order as cancel/submit.
            cur.execute('SELECT uid FROM sherlock_access WHERE uid=(SELECT uid FROM sherlock_requests WHERE id=%s) FOR UPDATE', (job['id'],))
            cur.execute("SELECT id FROM sherlock_requests WHERE id=%s AND lease_token=%s AND status='researching' AND lease_until>NOW() FOR UPDATE", (job['id'], job['token']))
            if not cur.fetchone():
                raise ResearchError('lease_lost', 'Worker lease is no longer valid.')
            status = 'awaiting_review' if report else ('insufficient_evidence' if error == 'insufficient_evidence' else 'failed')
            cur.execute('UPDATE sherlock_requests SET status=%s,stage=%s,report=%s::jsonb,review=%s::jsonb,error_code=%s,lease_token=NULL,lease_until=NULL WHERE id=%s',
                        (status, status, json.dumps(report), json.dumps(review), error, job['id']))
            if not report:
                self._refund(cur, job['id'])

    def expire(self):
        # Snapshot, then owner-first locks; a live worker is fenced by token/status.
        with transaction(self.db) as cur:
            cur.execute("SELECT id,uid FROM sherlock_requests WHERE (status='researching' AND lease_until<NOW()) OR (status='queued' AND due_at<NOW())")
            rows = cur.fetchall()
        for request_id, uid in rows:
            with transaction(self.db) as cur:
                cur.execute('SELECT uid FROM sherlock_access WHERE uid=%s FOR UPDATE', (uid,))
                cur.execute("UPDATE sherlock_requests SET status='failed',stage='failed',error_code='worker_expired',lease_token=NULL,lease_until=NULL WHERE id=%s AND ((status='researching' AND lease_until<NOW()) OR (status='queued' AND due_at<NOW())) RETURNING id", (request_id,))
                if cur.fetchone():
                    self._refund(cur, request_id)

    def purge_artifacts(self):
        with transaction(self.db) as cur:
            cur.execute("DELETE FROM sherlock_artifacts WHERE created_at<NOW()-INTERVAL '30 days'")
            return cur.rowcount
