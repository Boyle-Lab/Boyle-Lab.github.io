---
layout: post
status: publish
title: Lab Celebrates 2023!
date: '2023-12-14'
external-url:
teaser: 2023/Holiday_Party.png
categories:
- Events
---

The Boyle Lab celebrates time together, new members, and those leaving at the end of the year! The lab sucessfully won the gingerbread house competition held by the department both in category (twizlers) and overall and then celebrated with Captain Sonar!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2023-12-14-Holiday_Party' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
