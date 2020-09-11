import setuptools

with open("README.md", "r") as file:
    long_description = file.read()

setuptools.setup(
    name="imp-py",
    version="0.0.1",
    description="Ion Package Manager",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitub.com/ionlang/ipm",
    packages=["ipm_py"],
    python_requires=">=3.5"
)
