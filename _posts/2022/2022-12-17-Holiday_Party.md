---
layout: post
status: publish
title: Holiday Hotpot Party!
date: '2022-12-17'
external-url:
teaser: 2022/sam_cooking.JPG
categories:
- Events
---

We enjoyed an end-of-year celebration with hotpot and a White Elephant gift exchange game!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2022-12-17-Holiday_Party' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
