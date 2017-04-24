---
layout: post
status: publish
title: Boyle Lab Holiday Party!
date: '2016-12-18'
external-url:
teaser: Holiday_party.png
categories:
- Events
---

The Boyle Lab celebrates the end of the year, Ningxin's graduation, and Shengcheng's prelim with a party!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2016-12-18-Holiday_Party' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
