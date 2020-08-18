import setuptools

setuptools.setup(
    name="un-GameBoy",
    version="0.1.0",
    author="Xavier Villaneau",
    packages=setuptools.find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "click",
        "prompt-tookit",
    ],
    entry_points={
        "console_scripts": [
            "ungameboy = ungameboy.prompt.application:run"
        ]
    }
)
