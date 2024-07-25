from src.celery.tasks import block_cards_test


balances = ['280bd3d9-c59d-4289-8e07-be667818781e']
block_cards_test.delay(balances)
