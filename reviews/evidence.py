"""Portable review evidence; no third-party or SpecRoad dependency."""
from .contracts import MAX_FILES, digest, require, validate_module, validate_review


def item_binding(module, item):
    """Other items do not invalidate an unchanged item and its complete criteria."""
    return digest(dict(format_version=1, module_id=module['id'], title=module['title'],
        purpose=module['purpose'], source=module['source'], criteria=module['criteria'],
        minimum_reviewers=module['minimum_reviewers'],
        section=next(s for s in module['sections'] if s['id'] == item['section']), item=item))


def assess(module, reviews):
    """Pure review aggregation. Accepted means reported review coverage, never release."""
    validate_module(module)
    require(type(reviews) is list and len(reviews) <= MAX_FILES, 'Invalid review inventory')
    for record in reviews:
        validate_review(record)
    items = {item['id']: item for item in module['items']}
    rows = {key: [] for key in items}
    stale = []
    seen = set()
    records = {record['id']: record for record in reviews}
    superseded = set()
    for record in reviews:
        for decision in record['decisions']:
            for old_id in decision.get('supersedes', []):
                require(old_id in records, 'Superseded record is missing')
                old = records[old_id]
                require(old['reviewer']['email'].casefold() == record['reviewer']['email'].casefold(), 'Cannot supersede another reviewer')
                require(old['created_at'] < record['created_at'], 'Supersession must advance time')
                targets = [d for d in old['decisions'] if d['item_id'] == decision['item_id']]
                require(len(targets) == 1 and targets[0]['item_sha256'] == decision['item_sha256'], 'Supersession has a different item binding')
                superseded.add((old_id, decision['item_id']))
    for review in sorted(reviews, key=lambda r: r.get('id', '')):
        validate_review(review)
        require(review['id'] not in seen, 'Duplicate review ID')
        seen.add(review['id'])
        require(review['module_id'] == module['id'], 'Wrong review module')
        for decision in review['decisions']:
            key = decision['item_id']
            if key not in items or decision['item_sha256'] != item_binding(module, items[key]):
                stale.append(dict(review_id=review['id'], item_id=key))
                continue
            require(items[key]['section'] in review['attestations'], 'Missing section attestation')
            require(not items[key]['required_note'] or decision['note'].strip(), 'Missing required evidence note')
            rows[key].append(dict(review_id=review['id'], reviewer=review['reviewer'],
                superseded=(review['id'], key) in superseded, **decision))
    results = []
    for key, item in items.items():
        decisions = rows[key]
        active = [d for d in decisions if not d['superseded']]
        approvals = {d['reviewer']['email'].casefold() for d in active if d['verdict'] == 'accept'}
        conflict = any(d['verdict'] != 'accept' for d in active)
        status = 'changes_requested' if conflict else ('accepted' if len(approvals) >= module['minimum_reviewers'] else 'pending')
        results.append(dict(id=key, section=item['section'], status=status, approvals=len(approvals), reviews=decisions))
    accepted = sum(row['status'] == 'accepted' for row in results)
    return dict(module_id=module['id'], module_sha256=digest(module), total=len(items), accepted=accepted,
        open=len(items)-accepted, review_coverage_complete=accepted == len(items), release_accepted=False,
        items=results, stale=stale)
