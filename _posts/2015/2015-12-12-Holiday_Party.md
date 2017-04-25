---
layout: post
status: publish
title: Boyle Lab Holiday Party!
date: '2015-12-12'
external-url:
teaser: 2015/Holiday.jpg
categories:
- Events
---

The Boyle Lab celebrates the end of the year with a party!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2015-12-12-Holiday_Party' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
