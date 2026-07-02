- I do not want my UI to have gradients, containers, etc. You will use the exact same UI I used for my other app: C:\Users\adm\.vscode\Products\Freelancing

- Do not add redundant/meaningless stuff, I want my flask app to run very fast, you could use flask compress if necessary.

- Design everythimng with data security in mind, because this is patient data, which is very sensitive

- Later, when we reach that point, you will create the example.env which I will reference the variables to ad keys to my actual .env

- I will be using MySQL database, not SQLite. I will also use Google auth and email login/Signup, with password reset. You can see the exact logic for this in my other app; C:\Users\adm\.vscode\Products\Freelancing

- Also you can see/borrow the logic for smtp and user account profile in my other app: C:\Users\adm\.vscode\Products\Freelancing

- You can also borrow concepts from; C:\Users\adm\.vscode\Products\Freelancing\ARCHITECTURE.md

- Also no emojis in my app, not even one, use only svgs and icons as in my other app; C:\Users\adm\.vscode\Products\Freelancing

- For the donors by a county-distance ranking, you need to implement mobile phone location access, or other means to get the exact location of an individual(eg by subcounty, or even ward/constituency level). This would be better than county level because some are too big. Update the donor and other profiles to include the updated/required fields.

- Restricted access for hospital and blood bank roles.

Ensure when the profile picture is clicked, it enlarges and can be fully viewed. I also do not like how the profile information in the profile section are arranged relative to the profile pictiures, it's a terrible design, update that so it's similar to my other app; C:\Users\adm\.vscode\Products\Freelancing. Also when a hospital clicks the donopr's page, they shopuld see their profile picture, the same applies to a donor, they should be able to see the hospital's profile picture in full. Also from the hospital side, when I click to view a donor's information it displays as if I'm the donor, this is a poor architecture(I could also see tre notification "You are currently eligible to donate blood!" from the hospital side), fix that, the same applies to the donor side, I dont want to open a Hospital's profile and see how they see it from their side

