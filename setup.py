from setuptools import setup

setup(
    name='training',
    version='0.1.0',
    packages=['training', 'training.server', 'training.client', 'training.tests'],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'server = training.server.__main__:main',
            'client = training.client.__main__:main'
        ]
    }
)