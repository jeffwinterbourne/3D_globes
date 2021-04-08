# 3D_globes

This repository to contains the code and methodology required to create 3D printable globes as per Koelemeijer and Winterbourne (2021), published in Frontiers in Earth Science (https://www.frontiersin.org/articles/10.3389/feart.2021.669095/abstract).  

![overview image](/Overview.JPEG)
_Example of how a coloured global map can be represented as a physical object._

## Overview
Measurements and models of global geophysical parameters such as potential fields, seismic velocity models and dynamic topography are well represented as traditional contoured and / or coloured maps. However, as teaching aids and for public engagement, they offer little impact. Modern 3D printing techniques help to visualise these and other concepts that are difficult to grasp, such as the intangible structures in the deep Earth. 

We have developed a simple method for portraying scalar fields by 3D printing modified globes of surface topography, representing the parameter of interest as additional, exaggerated topography. This is particularly effective for long-wavelength (>500 km) fields. The workflow uses only open source and free-to-use software, and the resulting models print easily and effectively on a cheap (<$300) desktop 3D printer. 

Some of our most effective models are simply exaggerated planetary topography in 3D, including Earth, Mars and the Moon. The resulting globes provide a powerful way to explain the importance of plate tectonics in shaping a planet and linking surface features to deeper dynamic processes. In addition, we have applied our workflow to models of crustal thickness, dynamic topography, the geoid and seismic tomography. By analogy to Russian nesting dolls, our "seismic matryoshkas" ave multiple layers that can be removed by the audience to explore the structures present deep within our planet and to learn about ongoing dynamic processes.

Handling our globes provokes new questions and draws attention to different features compared with 2D maps. Our globes are complementary to traditional methods of representing geophysical data, aiding learning through touch and intuition and making education and outreach more inclusive for the visually impaired and students with learning disabilities. 

## Contents:
 - 3D_modelling_tutorial.pdf: step-by-step tutorial for modelling 3D globes in Blender and preparing for 3D printing
 - composite_images_to_bump_map.ipynb: ipython notebook for compositing height maps

