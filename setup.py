from setuptools import setup, find_packages
import os

version = '1.0'

setup(name='pretaweb.funnelweb',
      version=version,
      description="",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
      keywords='transmogrifier blueprint funnelweb source plone import conversion microsoft office',
      author='Dylan Jay',
      author_email='software@pretaweb.com',
      url='http://www.pretaweb.com',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['pretaweb'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          # -*- Extra requirements: -*-
          'lxml==2.1.1',
          'BeautifulSoup',
          'collective.transmogrifier',
          'plone.app.transmogrifier',
          'plone.i18n'
          ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )