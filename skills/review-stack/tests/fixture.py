"""A synthetic three-PR stack (gift cards at checkout) and the compact explainer record a reviewer writes for it.

Shared by the renderer tests and make_demo.py. Every value is fictional.
"""

from pathlib import Path
import subprocess

TRUNK = {
    'src/models/order.ts': """export interface Order {
  id: string;
  businessId: string;
  totalMinor: number;
  currency: string;
  status: 'pending' | 'paid' | 'refunded';
}
""",
    'src/checkout/pay.ts': """import { Order } from '../models/order';
import { gateway } from '../payments/gateway';

export async function pay(order: Order) {
  const charge = await gateway.charge(order.totalMinor, order.currency);
  order.status = 'paid';
  return charge;
}
""",
    'src/payments/gateway.ts': """export const gateway = {
  async charge(amountMinor: number, currency: string) {
    return { amountMinor, currency, id: 'ch_demo' };
  },
};
""",
}

SCHEMA = {
    'src/models/giftCard.ts': """export interface GiftCard {
  id: string;
  businessId: string;
  code: string;
  balanceMinor: number;
  currency: string;
  expiresAt: Date;
  status: 'active' | 'used' | 'expired';
}

export const giftCardIndexes = [
  { fields: { businessId: 1, code: 1 }, unique: true },
];
""",
    'src/models/order.ts': """export interface Order {
  id: string;
  businessId: string;
  totalMinor: number;
  currency: string;
  status: 'pending' | 'paid' | 'refunded';
  giftCardId?: string;
  giftCardMinor?: number;
}
""",
    'src/migrations/20261120-gift-cards.ts': """export async function up(db) {
  await db.createCollection('giftcards');
  await db.collection('giftcards').createIndex({ businessId: 1, code: 1 }, { unique: true });
}

export async function down(db) {
  await db.collection('giftcards').drop();
}
""",
}

REDEEM = {
    'src/routes/giftCards.ts': """import { router, requireBusiness } from '../http';
import { redeem } from '../giftCards/redeem';

router.post('/orders/:id/gift-card', requireBusiness, async (req, res) => {
  const result = await redeem(req.params.id, req.body.code);
  res.json({ appliedMinor: result.appliedMinor, remainingMinor: result.remainingMinor });
});
""",
    'src/giftCards/redeem.ts': """import { db } from '../db';

export async function redeem(orderId: string, code: string) {
  const order = await db.orders.findById(orderId);
  const card = await db.giftcards.findOne({ code, status: 'active' });
  const appliedMinor = Math.min(card.balanceMinor, order.totalMinor);
  card.balanceMinor -= appliedMinor;
  await card.save();
  order.giftCardId = card.id;
  order.giftCardMinor = appliedMinor;
  await order.save();
  return { appliedMinor, remainingMinor: order.totalMinor - appliedMinor };
}
""",
    'src/checkout/pay.ts': """import { Order } from '../models/order';
import { gateway } from '../payments/gateway';

export async function pay(order: Order) {
  const dueMinor = order.totalMinor - (order.giftCardMinor ?? 0);
  const charge = await gateway.charge(dueMinor, order.currency);
  order.status = 'paid';
  return charge;
}
""",
}

EXPIRY = {
    'src/jobs/expireGiftCards.ts': """import { db } from '../db';

export async function expireGiftCards(now: Date) {
  await db.giftcards.updateMany(
    { status: 'active', expiresAt: { $lt: now } },
    { $set: { status: 'expired' } },
  );
}
""",
    'src/jobs/schedule.ts': """import { schedule } from '../scheduler';
import { expireGiftCards } from './expireGiftCards';

schedule('0 * * * *', () => expireGiftCards(new Date()));
""",
}


def make_repo(repo):
    """Create the fixture repository; returns the commit for trunk and each PR head."""
    repo = Path(repo)
    repo.mkdir(parents=True)

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

    git('init', '-q')
    git('config', 'user.name', 'Fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    shas = {}
    for name, files in (('trunk', TRUNK), ('schema', SCHEMA), ('redeem', REDEEM), ('expiry', EXPIRY)):
        for path, text in files.items():
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git('add', '.')
        git('commit', '-qm', name)
        shas[name] = git('rev-parse', 'HEAD')
    return shas


def demo_record(repo, shas):
    """The compact form a reviewer writes: shorthand sources, defaulted revisions, declarative diagrams."""
    def pr(number, base, head, title, role, code_verdict):
        return {'id': f'server-{number}', 'repo': 'acme/shop-api', 'number': number, 'title': title, 'role': role,
                'repo_path': str(repo), 'base': shas[base], 'head': shas[head], 'scope': 'reviewed',
                'spec_verdict': 'No requirements source; reviewed against the PR title.', 'code_verdict': code_verdict}

    return {
        'title': 'Demo · gift cards at checkout',
        'summary': 'Synthetic example. Three stacked PRs add gift cards: a new collection, a redeem endpoint that '
                   'discounts checkout, and an hourly expiry job.',
        'limitations': 'Synthetic fixture: source reading only, no app, database or tests were run.',
        'story': {
            'users': 'Shoppers can pay part or all of an order with a gift card code. The card balance drops by the '
                     'amount used, and cards past their expiry date stop working within the hour.',
            'why': 'Inferred from the PR titles: businesses want to sell gift cards. No spec is linked.',
            'matters': [
                {'reason': 'permissions', 'finding': 'F1',
                 'text': "A shopper at one business can spend another business's card: redeem looks the code up "
                         'without the business.'},
                {'reason': 'concurrency', 'finding': 'F2',
                 'text': 'Two checkouts using one card at the same moment can both spend its full balance.'},
                {'reason': 'migration', 'text': "Rolling back #11 after launch deletes every sold card: the migration's "
                                                'down() drops the collection.',
                 'evidence': ['server-11:src/migrations/20261120-gift-cards.ts:6-8#drop']},
                {'reason': 'money', 'text': 'Checkout now charges the order total minus the gift card amount, in minor units.',
                 'evidence': ['server-12:src/checkout/pay.ts:5#giftCardMinor']}],
            'deploy': ['shop-api #11: run the migration (creates giftcards and its unique index)',
                       'shop-api #12: redeem endpoint and checkout discount',
                       'shop-api #13: hourly expiry job']},
        'sections': {
            'architecture': 'A shopper enters a code on an order. The new route hands it to redeem(), which finds the '
                            'card, subtracts what the order needs from its balance and records the amount on the order. '
                            'At payment, pay() charges the order total minus that amount. Separately, an hourly job '
                            'marks cards past their expiry date as expired.',
            'data': 'giftcards is a new collection, unique by business and code. Orders gain two optional fields that '
                    'point at the card and hold the amount it covered; existing orders are untouched.',
            'rollout': 'Everything is additive until cards are sold. After that the migration is one-way in practice: '
                       'its down() drops the collection with every remaining balance.',
            'contracts': 'One new endpoint. No existing request or response changes shape.',
            'lifecycle': 'Cards start active and become expired when the hourly job finds their expiry date passed. '
                         'The model also declares a used state, but no code sets it.'},
        'prs': [
            pr(11, 'trunk', 'schema', 'Add the gift card collection', 'Data: the giftcards collection, its unique index, '
               'and two optional order fields.', 'No findings.'),
            pr(12, 'schema', 'redeem', 'Redeem gift cards at checkout', 'Behaviour: the redeem endpoint and the checkout '
               'discount.', 'Changes needed: 2 High.'),
            pr(13, 'redeem', 'expiry', 'Expire gift cards hourly', 'Job: the hourly expiry sweep.', 'One Medium.')],
        'dependencies': [{'chain': ['server-11', 'server-12', 'server-13'], 'label': 'parent of',
                          'evidence': [{'kind': 'command', 'label': 'stack ancestry',
                                        'detail': 'Synthetic fixture: each PR is the next commit on the previous head.'}]}],
        'visuals': [
            {'id': 'arch', 'kind': 'graph', 'section': 'architecture', 'prs': ['server-12'],
             'title': 'Where gift cards plug in',
             'caption': 'The redeem endpoint writes to the new giftcards collection and to the order; checkout charges '
                        'what is left; an hourly job expires old cards.',
             'nodes': [
                 {'id': 'shopper', 'label': 'Shopper', 'shape': 'actor'},
                 {'id': 'route', 'label': 'POST /orders/:id/gift-card', 'detail': 'business-scoped route',
                  'status': 'new', 'src': 'src/routes/giftCards.ts:4#gift-card'},
                 {'id': 'redeem', 'label': 'redeem()', 'detail': 'applies the balance to the order', 'status': 'new',
                  'src': 'src/giftCards/redeem.ts:3-13#redeem'},
                 {'id': 'checkout', 'label': 'pay()', 'detail': 'charges total minus gift card', 'status': 'changed',
                  'src': 'src/checkout/pay.ts:5#giftCardMinor'},
                 {'id': 'cards', 'label': 'giftcards', 'shape': 'store', 'status': 'new',
                  'src': 'server-11:src/migrations/20261120-gift-cards.ts:2#giftcards'},
                 {'id': 'orders', 'label': 'orders', 'shape': 'store', 'status': 'changed',
                  'src': 'server-11:src/models/order.ts:7-8'},
                 {'id': 'gateway', 'label': 'Payment gateway', 'shape': 'external', 'src': 'src/payments/gateway.ts:2#charge'},
                 {'id': 'job', 'label': 'expireGiftCards', 'detail': 'every hour', 'shape': 'queue', 'status': 'new',
                  'src': 'server-13:src/jobs/schedule.ts:4#expireGiftCards'}],
             'edges': [
                 {'from': 'shopper', 'to': 'route', 'label': 'enters a code'},
                 {'from': 'route', 'to': 'redeem'},
                 {'from': 'redeem', 'to': 'cards', 'label': 'lowers balance'},
                 {'from': 'redeem', 'to': 'orders', 'label': 'records amount'},
                 {'from': 'shopper', 'to': 'checkout', 'label': 'pays'},
                 {'from': 'checkout', 'to': 'gateway', 'label': 'charges the rest'},
                 {'from': 'job', 'to': 'cards', 'label': 'expires', 'dashed': True}]},
            {'id': 'redeem-seq', 'kind': 'sequence', 'section': 'architecture', 'prs': ['server-12'],
             'title': 'Redeeming a code, step by step',
             'caption': 'From the shopper entering a code to paying. The two High findings sit on steps 3 and 4.',
             'participants': [
                 {'id': 'shopper', 'label': 'Shopper', 'shape': 'actor'},
                 {'id': 'route', 'label': 'Gift card route', 'status': 'new', 'src': 'src/routes/giftCards.ts:4'},
                 {'id': 'redeem', 'label': 'redeem()', 'status': 'new', 'src': 'src/giftCards/redeem.ts:3#redeem'},
                 {'id': 'db', 'label': 'MongoDB', 'shape': 'store'},
                 {'id': 'pay', 'label': 'pay()', 'status': 'changed', 'src': 'src/checkout/pay.ts:4#pay'}],
             'messages': [
                 {'from': 'shopper', 'to': 'route', 'label': 'POST a code for an order', 'src': 'src/routes/giftCards.ts:4-5'},
                 {'from': 'route', 'to': 'redeem', 'label': 'redeem(orderId, code)', 'src': 'src/routes/giftCards.ts:5#redeem'},
                 {'from': 'redeem', 'to': 'db', 'label': 'find the active card by code', 'detail': 'no business filter',
                  'tone': 'affected', 'src': 'src/giftCards/redeem.ts:5#findOne'},
                 {'from': 'redeem', 'to': 'db', 'label': 'save balance minus amount', 'detail': 'read, subtract, write',
                  'tone': 'affected', 'src': 'src/giftCards/redeem.ts:6-8#balanceMinor'},
                 {'from': 'redeem', 'to': 'db', 'label': 'save the order with the gift card amount',
                  'src': 'src/giftCards/redeem.ts:9-11#giftCardMinor'},
                 {'from': 'route', 'to': 'shopper', 'label': 'applied and remaining amounts', 'reply': True,
                  'src': 'src/routes/giftCards.ts:6#remainingMinor'},
                 {'from': 'shopper', 'to': 'pay', 'label': 'pay the order', 'src': 'src/checkout/pay.ts:4'},
                 {'from': 'pay', 'to': 'pay', 'label': 'due = total − gift card', 'src': 'src/checkout/pay.ts:5#giftCardMinor'}]},
            {'id': 'data-model', 'kind': 'schema', 'section': 'data', 'prs': ['server-11'],
             'title': 'One new collection, two new order fields',
             'caption': 'Added fields are marked +. Only changed fields and the order total are shown.',
             'entities': [
                 {'id': 'giftcards', 'label': 'giftcards', 'status': 'new', 'src': 'src/models/giftCard.ts:1-9#GiftCard',
                  'fields': [
                      {'name': 'businessId', 'type': 'string', 'status': 'added', 'index': 'unique with code',
                       'src': 'src/models/giftCard.ts:3'},
                      {'name': 'code', 'type': 'string', 'status': 'added', 'index': 'unique with businessId',
                       'src': 'src/models/giftCard.ts:4'},
                      {'name': 'balanceMinor', 'type': 'number, minor units', 'status': 'added',
                       'src': 'src/models/giftCard.ts:5'},
                      {'name': 'currency', 'type': 'string', 'status': 'added', 'src': 'src/models/giftCard.ts:6'},
                      {'name': 'expiresAt', 'type': 'Date', 'status': 'added', 'src': 'src/models/giftCard.ts:7'},
                      {'name': 'status', 'type': 'active | used | expired', 'status': 'added',
                       'src': 'src/models/giftCard.ts:8'}]},
                 {'id': 'orders', 'label': 'orders', 'status': 'changed', 'src': 'src/models/order.ts:1-9#Order',
                  'fields': [
                      {'name': 'totalMinor', 'type': 'number'},
                      {'name': 'giftCardId', 'type': 'string, optional', 'status': 'added', 'note': 'set by redeem',
                       'src': 'src/models/order.ts:7'},
                      {'name': 'giftCardMinor', 'type': 'number, optional', 'status': 'added',
                       'note': 'subtracted at checkout', 'src': 'src/models/order.ts:8'}]}],
             'relations': [{'from': 'orders', 'to': 'giftcards', 'label': 'giftCardId'}]},
            {'id': 'rollout-plan', 'kind': 'timeline', 'section': 'rollout', 'prs': ['server-11'],
             'title': 'Ship in stack order', 'caption': 'Each step needs the one before it.',
             'steps': [
                 {'kind': 'migrate', 'title': 'Create giftcards and its unique index',
                  'detail': "#11 · down() drops every card", 'reversible': False,
                  'src': 'src/migrations/20261120-gift-cards.ts:1-8#createIndex'},
                 {'kind': 'deploy', 'title': 'Redeem endpoint and checkout discount', 'detail': '#12 · reads giftcards',
                  'src': 'server-12:src/routes/giftCards.ts:4'},
                 {'kind': 'job', 'title': 'Hourly expiry sweep', 'detail': '#13', 'reversible': True,
                  'src': 'server-13:src/jobs/schedule.ts:4'}]},
            {'id': 'api', 'kind': 'table', 'section': 'contracts', 'prs': ['server-12'], 'title': 'API changes',
             'caption': 'One new endpoint; nothing existing changes shape.',
             'columns': ['Surface', 'Change', 'Request → response', 'Impact', 'Consumers'],
             'rows': [{'id': 'redeem-endpoint', 'tone': 'new', 'src': 'src/routes/giftCards.ts:4-6',
                       'cells': ['POST /orders/:id/gift-card', 'new endpoint',
                                 '{ code } → { appliedMinor, remainingMinor }', 'additive',
                                 'checkout UI (not in this stack)']}]},
            {'id': 'card-states', 'kind': 'graph', 'section': 'lifecycle', 'prs': ['server-13'],
             'title': "A gift card's life", 'caption': 'Only the hourly job changes a status; nothing marks a card used.',
             'nodes': [
                 {'id': 'active', 'label': 'active', 'detail': 'balance can be spent', 'status': 'new',
                  'src': 'server-11:src/models/giftCard.ts:8#active'},
                 {'id': 'expired', 'label': 'expired', 'detail': 'set by the hourly job', 'status': 'new',
                  'src': 'src/jobs/expireGiftCards.ts:5-6#expired'},
                 {'id': 'used', 'label': 'used', 'detail': 'declared, never set', 'tone': 'context'}],
             'edges': [{'from': 'active', 'to': 'expired', 'label': 'expiry date passed'},
                       {'from': 'active', 'to': 'used', 'label': 'never happens', 'dashed': True}]}],
        'decisions': [
            {'id': 'D1', 'title': 'The balance lives on the card', 'basis': 'inferred',
             'why': 'redeem lowers the card balance and records the applied amount on the order, so one card can be '
                    'spent across several orders.',
             'alternatives': 'A ledger of redemptions would make concurrent spends and refunds auditable.',
             'evidence': ['server-12:src/giftCards/redeem.ts:6-10']},
            {'id': 'D2', 'title': 'Expiry is an hourly sweep, not a check at redeem', 'basis': 'inferred',
             'why': 'The job flips status in bulk; redeem only looks for active cards.',
             'evidence': ['server-13:src/jobs/expireGiftCards.ts:3-8']}],
        'findings': [
            {'id': 'F1', 'pr': 'server-12', 'severity': 'High', 'title': "Redeem accepts another business's gift card",
             'explanation': 'The card lookup filters by code and status only; the route checks the business but redeem never uses it.',
             'impact': "A shopper at business A can spend a card sold by business B when their codes match.",
             'scenario': 'Business B sells code XMAS25. A shopper at business A enters XMAS25: redeem finds B\'s card and lowers its balance.',
             'fix': "Filter by the order's business: findOne({ businessId: order.businessId, code, status: 'active' }).",
             'evidence': ['src/giftCards/redeem.ts:5#findOne'], 'at': ['redeem-seq/3', 'arch/redeem']},
            {'id': 'F2', 'pr': 'server-12', 'severity': 'High', 'title': 'Two checkouts can spend the same balance',
             'explanation': 'redeem reads the balance, subtracts in memory and saves, so concurrent redeems both see the full balance.',
             'impact': 'A card worth 50 can cover two 50 orders when both redeem at once.',
             'scenario': 'Two tabs redeem a 5000-minor card on 5000-minor orders at the same time: both read 5000, both save 0, both orders are discounted 5000.',
             'fix': "Use one conditional update: updateOne({ _id, balanceMinor: { $gte: amount } }, { $inc: { balanceMinor: -amount } }).",
             'evidence': ['src/giftCards/redeem.ts:6-8#balanceMinor'], 'at': ['redeem-seq/4']},
            {'id': 'F3', 'pr': 'server-13', 'severity': 'Medium', 'title': 'Expired cards stay spendable for up to an hour',
             'explanation': 'redeem does not check expiresAt; only the hourly job changes the status.',
             'impact': 'A card can be spent up to 59 minutes after it expires.',
             'scenario': 'A card expiring at 10:01 is redeemed at 10:30; the next sweep runs at 11:00.',
             'fix': 'Add expiresAt: { $gt: now } to the redeem lookup.',
             'evidence': ['src/jobs/schedule.ts:4#0 * * * *', 'server-12:src/giftCards/redeem.ts:5#status'],
             'at': ['card-states/expired']}],
        'requirements': [],
        'checks': [{'pr': 'server-12', 'label': 'Redeem against a real database', 'status': 'not run',
                    'result': 'The synthetic fixture has no database.'}],
        'dropped': []}
