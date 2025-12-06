from setuptools import setup, find_packages
from erpnextkta import __version__ as version  # <-- tek kaynak burası

setup(
    name='erpnextkta',
    version=version,
    description='Custom app for ERPNext - KTA',
    author='KTA',
    author_email='erp@kta-endustri.com.tr',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=['frappe']
)
