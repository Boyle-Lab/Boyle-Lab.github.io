---
layout: post
status: publish
title: Pumpkin Carving!
date: '2017-10-21'
external-url:
teaser: 2017/Pumpkin_Carving.jpg
categories:
- Events
---

The Boyle Lab celebrates new lab members and successful funding in the lab with a pumpkin carving competition! Shengcheng and Haley had the top voted pumpkins, but a great showing all around!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2017-10-21-Pumpkin_Carving' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
