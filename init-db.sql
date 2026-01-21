-- Initialize databases and users for platform services
-- This runs automatically on first postgres start

-- Create IEOMD database and user
CREATE USER ieomd WITH PASSWORD 'CHANGE_ME_IEOMD';
CREATE DATABASE ieomd_db OWNER ieomd;
GRANT ALL PRIVILEGES ON DATABASE ieomd_db TO ieomd;

-- Create Umami database and user
CREATE USER umami WITH PASSWORD 'CHANGE_ME_UMAMI';
CREATE DATABASE umami_db OWNER umami;
GRANT ALL PRIVILEGES ON DATABASE umami_db TO umami;

-- Create Synapse (Matrix) database and user
CREATE USER synapse WITH PASSWORD 'CHANGE_ME_SYNAPSE';
CREATE DATABASE synapse_db
  OWNER synapse
  ENCODING 'UTF8'
  LC_COLLATE='C'
  LC_CTYPE='C'
  TEMPLATE template0;
GRANT ALL PRIVILEGES ON DATABASE synapse_db TO synapse;
