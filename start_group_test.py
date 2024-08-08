from src.celery_tasks.main import main_chain

main_chain.delay()
