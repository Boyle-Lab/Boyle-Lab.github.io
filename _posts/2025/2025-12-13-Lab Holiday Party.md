---
layout: post
published: true
title: Lab Holiday Party!
date: '2025-12-13'
external-url:
teaser: 2025/holiday_group.jpg
categories:
- Events
---

The lab celebrated the end of another great year with food, sweets, and games!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2025-12-13-Holiday_Party' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
