import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="draconic-interpreter",
    version="0.0.1",
    author="Andrew Zhu",
    author_email="andrew@zhu.codes",
    description="The interpreter for the Draconic scripting language.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/avrae/draconic",
    packages=setuptools.find_packages(exclude=("tests",)),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
