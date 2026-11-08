"""Optional hosted Stripe checkout. No card details are handled by BACity."""
import hashlib
import hmac
import json
import time
from typing import Literal
from uuid import UUID
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.core.community import require_verified, owned_organization, rate_limit
from app.models.community import Organization, BillingReceipt

router = APIRouter(prefix='/billing', tags=['billing'])


def stripe(method, path, data=None, key=None):
    settings = get_settings()
    headers = {'Authorization': 'Bearer ' + settings.stripe_secret_key}
    if key:
        headers['Idempotency-Key'] = key
    try:
        response = httpx.request(method, 'https://api.stripe.com/v1/' + path, data=data, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, 'Billing provider unavailable; please try again')


@router.get('/status')
def status():
    s = get_settings()
    return {'configured': bool(s.stripe_secret_key and s.stripe_webhook_secret),
            'plans': [tier for tier, price in [('pro', s.stripe_pro_price_id), ('business', s.stripe_business_price_id)] if price and s.stripe_secret_key and s.stripe_webhook_secret]}


class Checkout(BaseModel):
    organization_id: UUID
    tier: Literal['pro', 'business']


@router.post('/checkout')
def checkout(payload: Checkout, user=Depends(require_verified), db: Session = Depends(get_db)):
    s = get_settings()
    price = s.stripe_pro_price_id if payload.tier == 'pro' else s.stripe_business_price_id
    if not s.stripe_secret_key or not s.stripe_webhook_secret or not price:
        raise HTTPException(503, 'Payments are not configured')
    rate_limit(db, 'checkout:' + str(user.id), 5)
    org = owned_organization(db, user, payload.organization_id)
    if not org.verified:
        raise HTTPException(403, 'Verify your organization first')
    if org.stripe_subscription_id:
        raise HTTPException(409, 'Use the billing portal to manage your existing subscription')
    if not org.stripe_customer_id:
        customer = stripe('POST', 'customers', {'name': org.name, 'email': user.email}, 'bacity-customer-' + str(org.id))
        org.stripe_customer_id = customer['id']
        db.commit()
    session = stripe('POST', 'checkout/sessions', {
        'mode': 'subscription', 'customer': org.stripe_customer_id,
        'client_reference_id': str(org.id), 'line_items[0][price]': price, 'line_items[0][quantity]': '1',
        'success_url': s.public_app_url.rstrip('/') + '/community?billing=success',
        'cancel_url': s.public_app_url.rstrip('/') + '/community?billing=cancelled',
    }, f'bacity-checkout-{org.id}-{payload.tier}-{int(time.time()) // 1800}')
    return {'url': session['url']}


@router.post('/portal/{identifier}')
def portal(identifier: UUID, user=Depends(require_verified), db: Session = Depends(get_db)):
    org = owned_organization(db, user, identifier)
    if not get_settings().stripe_secret_key or not org.stripe_customer_id:
        raise HTTPException(503, 'Billing is not configured for this organization')
    return {'url': stripe('POST', 'billing_portal/sessions', {'customer': org.stripe_customer_id, 'return_url': get_settings().public_app_url.rstrip('/') + '/community'})['url']}


def verify_signature(body, signature, secret):
    try:
        parts = [part.split('=', 1) for part in signature.split(',')]
        timestamp = next(value for key, value in parts if key == 't')
        if abs(time.time() - int(timestamp)) > 300:
            return False
        expected = hmac.new(secret.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
        return any(key == 'v1' and hmac.compare_digest(expected, value) for key, value in parts)
    except (ValueError, StopIteration):
        return False


@router.post('/webhook')
async def webhook(request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    if not s.stripe_webhook_secret or not s.stripe_secret_key:
        raise HTTPException(503, 'Payments are not configured')
    body = await request.body()
    if len(body) > 262144 or not verify_signature(body, request.headers.get('stripe-signature', ''), s.stripe_webhook_secret):
        raise HTTPException(400, 'Invalid webhook signature')
    try:
        event = json.loads(body)
        event_id, kind, obj = event['id'], event['type'], event['data']['object']
        if not isinstance(event_id, str) or len(event_id) > 200:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, 'Invalid webhook payload')
    # Serialize provider events across replicas. Current provider state handles out-of-order delivery.
    if db.bind.dialect.name == 'postgresql':
        from sqlalchemy import text
        db.execute(text('SELECT pg_advisory_xact_lock(82619423)'))
    if db.get(BillingReceipt, event_id):
        return {'received': True}
    if kind in ('checkout.session.completed', 'customer.subscription.created', 'customer.subscription.updated', 'customer.subscription.deleted'):
        org = db.query(Organization).filter_by(stripe_customer_id=obj.get('customer')).first() if obj.get('customer') else None
        if org:
            subscriptions = stripe('GET', 'subscriptions?customer=' + org.stripe_customer_id + '&status=all&limit=100')
            org.tier, org.stripe_subscription_id = 'free', None
            for sub in subscriptions['data']:
                if sub['status'] not in ('active', 'trialing'):
                    continue
                prices = {i['price']['id'] for i in sub['items']['data']}
                tier = 'business' if s.stripe_business_price_id in prices else 'pro' if s.stripe_pro_price_id in prices else 'free'
                if tier != 'free' and (org.tier != 'business'):
                    org.tier, org.stripe_subscription_id = tier, sub['id']
    db.add(BillingReceipt(id=event_id))
    db.commit()
    return {'received': True}
