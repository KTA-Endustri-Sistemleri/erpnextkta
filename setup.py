from setuptools import setup, find_packages

setup(
    name='erpnextkta',
    version='0.0.1',
    description='Custom app for ERPNext - KTA',
    author='KTA',
    author_email='erp@kta-endustri.com.tr',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=['frappe']
)
