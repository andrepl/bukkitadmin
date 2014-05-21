import bukkitadmin

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


packages = [
    'bukkitadmin',
]

requires = [
    'pager>=3.3',
    'argcomplete>=0.8.0',
    'progressbar>=2.3',
    'beautifulsoup4>=4.3.2',
    'feedparser>=5.1.3',
    'requests>=1.2.3',
    'pyyaml>=3.10',
    'pexpect>=2.4',
]

setup(
    name = "bukkitadmin",
    version = bukkitadmin.__version__,
    packages = packages,
    install_requires=requires,
    zip_safe=False,
    package_dir={'bukkitadmin': 'bukkitadmin'},
    entry_points = {
        'console_scripts': [
            'bukkit = bukkitadmin.commands:main'
        ]
    }
)
