---
layout: post
status: publish
title: Pumpkin Carving!
date: '2021-10-31'
external-url:
teaser: 2021/Pumpkin_Carving.png
categories:
- Events
---

The Boyle Lab celebrates time together with pumpkin carving and trick-or-treating! 

<div>
{% for image in site.static_files %}
    {% if image.path contains '2021-10-31-Pumpkin_Carving' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
