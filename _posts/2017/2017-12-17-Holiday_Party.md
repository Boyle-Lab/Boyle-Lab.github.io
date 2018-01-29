---
layout: post
status: publish
title: Boyle Lab Holiday Party!
date: '2017-12-17'
external-url:
teaser: 2017/Holiday_party.png
categories:
- Events
---

The Boyle Lab celebrates the end of another great year with many passed prelims and new papers on the way!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2017-12-17-Holiday_Party' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
