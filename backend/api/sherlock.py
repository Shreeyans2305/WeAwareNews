"""Authenticated website-only research endpoints. No billing or mail side effects."""
import os
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from research.store import Store, ResearchError


class Investigation(BaseModel):
    class Config:
        extra = 'forbid'

    question: str = Field(..., min_length=20, max_length=1200)
    scope: str = Field('', max_length=600)
    reportLength: Literal['brief', 'standard', 'detailed'] = 'standard'
    submissionKey: str = Field(..., min_length=16, max_length=80, pattern=r'^[a-zA-Z0-9-]+$')


def create_router(get_db, verify_user):
    router = APIRouter(prefix='/api/v1/sherlock', tags=['Sherlock Mode'])

    def owner(claims=Depends(verify_user)):
        uid = claims.get('uid') or claims.get('sub')
        if not uid:
            raise HTTPException(401, 'Account identity is missing.')
        if not claims.get('email_verified'):
            raise HTTPException(403, 'Verify your email address before using Sherlock Mode.')
        return uid

    def call(fn, *args):
        try:
            return fn(*args)
        except ResearchError as exc:
            raise HTTPException(exc.status, {'code': exc.code, 'message': exc.message}) from exc

    @router.get('/entitlement')
    def entitlement(uid=Depends(owner), claims=Depends(verify_user), db=Depends(get_db)):
        if os.getenv('SHERLOCK_ENABLED') != 'true':
            return {'eligible': False, 'credits': 0, 'acceptingRequests': False, 'expiresAt': None}
        call(Store(db).redeem_invite, uid, claims.get('email'))
        return call(Store(db).access, uid)

    @router.post('/requests', status_code=202)
    def submit(payload: Investigation, uid=Depends(owner), claims=Depends(verify_user), db=Depends(get_db)):
        if os.getenv('SHERLOCK_ENABLED') != 'true':
            raise HTTPException(503, 'Sherlock Mode is not accepting investigations yet.')
        question = payload.question.strip()
        if len(question) < 20:
            raise HTTPException(422, 'Please ask a specific research question of at least 20 characters.')
        call(Store(db).redeem_invite, uid, claims.get('email'))
        request_id = call(Store(db).submit, uid, question, payload.scope.strip(), payload.submissionKey, payload.reportLength)
        return {'id': request_id}

    @router.get('/requests')
    def history(uid=Depends(owner), db=Depends(get_db)):
        if os.getenv('SHERLOCK_ENABLED') != 'true':
            return {'requests': []}
        return {'requests': call(Store(db).listing, uid)}

    @router.get('/requests/{request_id}')
    def detail(request_id: str, uid=Depends(owner), db=Depends(get_db)):
        return call(Store(db).detail, uid, request_id)

    @router.get('/requests/{request_id}/report.pdf')
    def pdf(request_id: str, uid=Depends(owner), db=Depends(get_db)):
        investigation = call(Store(db).detail, uid, request_id)
        if investigation['status'] != 'completed' or not investigation['report']:
            raise HTTPException(409, 'The PDF is available after editor approval.')
        from research.pdf import render_report_pdf
        content = render_report_pdf(investigation)
        # Stable filename never includes user input; no public object URLs, file
        # paths, shared caches, extra model calls or stored unreviewed PDFs.
        return Response(content, media_type='application/pdf', headers={
            'Content-Disposition': 'attachment; filename="weaware-sherlock-report.pdf"',
            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        })

    @router.post('/requests/{request_id}/cancel')
    def cancel(request_id: str, uid=Depends(owner), db=Depends(get_db)):
        call(Store(db).cancel, uid, request_id)
        return {'status': 'cancelled'}

    return router
