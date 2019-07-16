from distutils.core import setup
import setuptools

setup(
    name='sync-repositories',
    packages=[
        'sync_repositories',
        'sync_repositories.credentials',
        'sync_repositories.repository'
    ],
    entry_points={
        'console_scripts': [
            'sync-repos = sync_repositories.__main__:_main'
        ]
    },
    version='0.1',
    license='MIT',
    description="""Helper script to automatically "update" (in some sense of
        the word) every source code repository you have""",
    author='Whisperity',
    author_email='whisperity@no.no',
    url='http://github.com/whisperity/sync-repositories',
    download_url='http://github.com/whisperity/sync-repositories/' +
                 'archive/v_01.tar.gz',
    keywords=['git', 'svn', 'repository', 'source control', 'version control'],
    install_requires=[
        'GitPython',
        'secretstorage',
        'svn'
    ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License'
        'Operating System :: POSIX :: Linux',
        'Operating System :: Unix',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ]
)
