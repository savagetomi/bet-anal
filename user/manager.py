from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(
            self, email, first_name,last_name,password=None,**extra_kwargs
    ):
        
        if not email:
            raise ValueError('Email is Required')
        if not first_name:
            raise ValueError("First Name is Required")
        if not last_name:
            raise ValueError("Last Name is Required")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            first_name = first_name,
            last_name = last_name,
            **extra_kwargs,
            )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    
