from distutils.core import setup

setup(name='cutaudio',
      author='Thomas Levine',
      author_email='_@thomaslevine.com',
      description='Cut an audio file into small pieces with nice names.',
      url='http://dada.pink/cutaudio',
      py_modules=['cutaudio'],
      entry_points = {'console_scripts': ['cutaudio = cutaudio:main']},
      install_requires = ['horetu'],
      version='0.0.1',
      license='AGPL',
      classifiers=[
          'Programming Language :: Python :: 3.5',
      ],
)
