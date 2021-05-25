from __future__ import absolute_import
from celery import Celery

app = Celery('celery_demo',
             broker='amqp://cameron:foxkilla@localhost/cameron_vhost',
             backend='rpc://',
             include=['celery_demo.tasks', 'training.server.db_utils', 'training', 'training.server', 'training.model', 'training.client.choice_funcs'])