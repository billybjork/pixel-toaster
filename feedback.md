# Feedback 

- you don't want people to have to run `pip install`. Instead you can ship a binary in github and have people just pull the binary
Create a release here: https://github.com/billybjork/pixel-toaster/releases

- create a proper entry point to your application 

- organize your cdoe more where the main.py just shows the different modes that your cli can run, and then imports code from your src directory.

- When someone pulls your toast binary, have it on the first run no mattter what go in and run commands to get people's input, such as
    - what device are you on 
    - what is your open api key 
    And then you save it to ~/.toast.conf or ~/.toastrc

- familiarize yourself with dotfiles

- When someone comes to you with problems, you will have nothing to be able to debug. Your initialization should save a `~/.toast.logs` as well as a `~/.toast.history`
- now that I am thinking about it, there should just be a directory created called `~/.toast_bjork` directory

- pass in a command that says " i want to check this ffmpeg command first before running it "
- use `makefile` stuff to create a binary of your project, and then a separate command to push and publish it to your github repo.
- in your makefile also add some stuff in for linters, this will make your code cleaner and give you automatic feedback 
    https://codilime.com/blog/python-code-quality-linters/
