---
layout: post
status: publish
title: Boyle Lab Summer BBQ!
date: '2016-07-17'
external-url:
teaser: 2016/Summer_BBQ.jpg
categories:
- Events
---

The Boyle Lab celebrates the beautiful summer and new members in the lab with a summer BBQ.

<div>
{% for image in site.static_files %}
    {% if image.path contains '2016-07-17-Summer_team_building' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
