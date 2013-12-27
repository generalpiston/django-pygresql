from distutils.core import setup

setup(
    name = "Django PyGreSQL",
    version = '0.1.0',
    author = 'Cloudera Inc.',
    author_email = 'abe@cloudera.com',
    description = 'A Django connector to PostgreSQL through PyGreSQL.',
    license="ASL2",
    packages=["django_pygresql"],
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Database',
        'Topic :: Database :: Front-Ends',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Operating System :: OS Independent'
   ],
)
