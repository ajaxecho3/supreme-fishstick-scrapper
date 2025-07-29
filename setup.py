from setuptools import setup, find_packages

setup(
    name='supreme_fishstick_scrapper',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[
        'requests',
        'beautifulsoup4',
        'pandas',
        'openpyxl',
        'matplotlib',
        'pytest'
    ],
    entry_points={
        'console_scripts': [
            'scraper=src.scraper:main'
        ]
    },
    description='A web scraper for research papers and data analysis.',
    author='ajaxecho3',
    license='MIT'
)
