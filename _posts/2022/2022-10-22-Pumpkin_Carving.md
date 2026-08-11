---
layout: post
published: true
title: Pumpkin Carving Party!
date: '2022-10-22'
external-url:
teaser: 2022/pumpkins.jpg
categories:
- Events
---

We showed off our pumpkin carving skills, enjoyed some good food, and played fun games!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2022-10-22-Pumpkin_Carving' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
