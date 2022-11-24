from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="arduino_coldfire_bdm",
    version="0.1.0",
    description=(
        "An interface to Motorola® Coldfire processors' Background Debug Interface (BDM) using an"
        " Arduino."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/psobot/arduino_coldfire_bdm",
    author="Peter Sobot",
    author_email="github@petersobot.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Debuggers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="coldfire, bdm, debugger, 68k, motorola, arduino",
    package_dir={"": "."},
    packages=["arduino_coldfire_bdm"],
    python_requires=">=3.6, <4",
    install_requires=["pySerial", "tqdm"],
    package_data={"arduino_coldfire_bdm": ["arduino-coldfire-bdm.ino"]},
    entry_points={
        "console_scripts": ["arduino-coldfire-bdm=arduino_coldfire_bdm.command_line:main"]
    },
)
