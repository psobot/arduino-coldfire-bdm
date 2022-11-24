# arduino-coldfire-bdm

An interface to Motorola® Coldfire processors' Background Debug Interface (BDM) using an Arduino.

```
pip install arduino-coldfire-bdm
```

## What?

A long long time ago (the mid-1990s), Motorola created a series of CPUs derived from the 68k architecture, called the Coldfire. These processors are largely obsolete today, but are still found in certain industrial equipment and embedded devices released around that time; including some vintage synthesizers, like [the Alesis A6 Andromeda](https://www.alesis.com/products/view/a6-andromeda).

This repository contains two things:
 - an Arduino sketch, which allows connecting pretty much any Arduino to a Coldfire processor's Background Debug Mode (BDM) port to send and receive data
 - a Python library to connect to an Arduino over USB serial, to allow running high-level debugging commands, like:
   - tracing execution (i.e.: like GDB or LLDB)
   - dumping the contents of memory to a file
   - erasing and re-flashing an attached flash memory chip
   - testing attached RAM chips
   - whatever else you want; it's Python! You can script it.

This library, when paired with an Arduino, performs many of the same functions as [PEMicro's _Multilink_ debugging probes](https://www.pemicro.com). This library is free, runs wherever you can run an Arduino and Python code (rather than just on Windows), and requires no drivers. However, this library is way slower, is missing a ton of functions, and has no IDE support.

## Why?

I bought a broken Alesis A6 Andromeda, and wanted to try fixing it by re-flashing its firmware without doing any soldering, because I'm bad at soldering. Read about that journey [on my blog](http://blog.petersobot.com/preview/c5fGNB81gvwoJvi7SchKEK/).

## Can I use this for other things?

Probably. There are certain assumptions made (especially around interfacing with Flash or RAM) that apply only to the Andromeda, and may not be useful for other devices. Pull requests to make this code more generic would be welcomed.

## What if I brick my device?

Here's the license; I take no responsibility if this software is misused. You should probably read it carefully first.

```
Copyright (c) 2022 Peter Sobot

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```