---
layout: post
status: publish
title: Lab surprises Jessica with a baby shower!
date: '2016-12-02'
external-url:
teaser: 2016/Baby_Shower.jpg
categories:
- Fun
---

The Boyle lab celebrates Jessica's first little girl on her way in December!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2016-12-02-Baby_Shower' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
