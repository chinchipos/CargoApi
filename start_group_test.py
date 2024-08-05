from src.celery.main import main_chain

main_chain.delay()
