---
layout: post
published: true
title: DCMB Holiday Party!
date: '2024-12-18'
external-url:
teaser: 2024/group_photo.jpg
categories:
- Events
---

The Boyle Lab created a masterpiece for the Gingerbread House competition at this year's DCMB Holiday Party! Our "Spirit House" sent us home with a trophy and a gift card to Panera!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2024-12-18-DCMB_Holiday' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
