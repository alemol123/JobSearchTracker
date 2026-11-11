-- Local only: run once by the db-init container in docker-compose.yml, as sa.
-- Creates one database per service and one login per service. Passwords are not
-- in this file: sqlcmd replaces $(PIPELINE_PW) and $(SKILLS_PW) with the
-- environment variables of the same name. Safe to run again (every step checks first).

IF DB_ID('pipeline') IS NULL CREATE DATABASE pipeline;
IF DB_ID('skills')   IS NULL CREATE DATABASE skills;
GO

IF SUSER_ID('pipeline_user') IS NULL CREATE LOGIN pipeline_user WITH PASSWORD = '$(PIPELINE_PW)';
IF SUSER_ID('skills_user')   IS NULL CREATE LOGIN skills_user   WITH PASSWORD = '$(SKILLS_PW)';
GO

-- Each login is a user in its own database only, so pipeline_user cannot open skills.
USE pipeline;
IF USER_ID('pipeline_user') IS NULL CREATE USER pipeline_user FOR LOGIN pipeline_user;
ALTER ROLE db_owner ADD MEMBER pipeline_user;
GO

USE skills;
IF USER_ID('skills_user') IS NULL CREATE USER skills_user FOR LOGIN skills_user;
ALTER ROLE db_owner ADD MEMBER skills_user;
GO
