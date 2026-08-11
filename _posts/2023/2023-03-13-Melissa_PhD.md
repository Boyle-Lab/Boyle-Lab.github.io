---
layout: post
published: true
title: Congratulations Dr. Englund!
date: '2023-03-13'
external-url:
teaser: 2023/Melissa_PhD.jpg
categories:
- Students
---

Melissa completed her Ph.D. defense today! She will be continuing on as a Scientist at the Chan Zuckerberg Biohub in Chicago! 
<br>
Congrats!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2023-03-13-Melissa_PhD' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
