
DROP TABLE IF EXISTS BlockEditAccess
;

DROP TABLE IF EXISTS BlockViewAccess
;

DROP TABLE IF EXISTS UserGroupMember
;

DROP TABLE IF EXISTS ReadRevision
;

DROP TABLE IF EXISTS BlockRelation
;

DROP TABLE IF EXISTS Block
;

DROP TABLE IF EXISTS User
;

DROP TABLE IF EXISTS UserGroup
;


CREATE TABLE UserGroup (
id INTEGER NOT NULL,
name VARCHAR(100) NOT NULL,

CONSTRAINT UserGroup_PK 
	PRIMARY KEY (id)
)
;


CREATE TABLE User (
id INTEGER NOT NULL,
name VARCHAR(100) NOT NULL,

CONSTRAINT User_PK 
	PRIMARY KEY (id)
)
;


CREATE TABLE Block (
id INTEGER NOT NULL,
latest_revision_id INTEGER NULL,
type_id INTEGER NOT NULL,
description VARCHAR(100) NULL,
UserGroup_id INTEGER NOT NULL,

CONSTRAINT Block_PK 
	PRIMARY KEY (id),
CONSTRAINT Block_id 
	FOREIGN KEY (UserGroup_id)
	REFERENCES UserGroup (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE
)
;


CREATE TABLE BlockRelation (
parent_block_specifier INTEGER NOT NULL,
parent_block_revision_id INTEGER NULL,
parent_block_id INTEGER NOT NULL,
Block_id INTEGER NOT NULL,

CONSTRAINT BlockRelation_PK
	PRIMARY KEY (Block_id),
CONSTRAINT BlockRelation_id 
	FOREIGN KEY (Block_id)
	REFERENCES Block (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE
)
;


CREATE TABLE ReadRevision (
revision_id INTEGER NOT NULL,
Block_id INTEGER NOT NULL,
User_id INTEGER NOT NULL,

CONSTRAINT ReadRevision_PK
	PRIMARY KEY (Block_id,User_id),
CONSTRAINT ReadRevision_id 
	FOREIGN KEY (Block_id)
	REFERENCES Block (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE,
CONSTRAINT ReadRevision_id 
	FOREIGN KEY (User_id)
	REFERENCES User (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE
)
;


CREATE TABLE UserGroupMember (
UserGroup_id INTEGER NOT NULL,
User_id INTEGER NOT NULL,

CONSTRAINT UserGroupMember_PK
	PRIMARY KEY (UserGroup_id,User_id),
CONSTRAINT UserGroupMember_id 
	FOREIGN KEY (UserGroup_id)
	REFERENCES UserGroup (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE,
CONSTRAINT UserGroupMember_id 
	FOREIGN KEY (User_id)
	REFERENCES User (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE
)
;


CREATE TABLE BlockViewAccess (
visible_from TIMESTAMP NOT NULL,
visible_to TIMESTAMP NULL,
Block_id INTEGER NOT NULL,
UserGroup_id INTEGER NOT NULL,

CONSTRAINT BlockViewAccess_PK
	PRIMARY KEY (Block_id,UserGroup_id),
CONSTRAINT BlockViewAccess_id 
	FOREIGN KEY (Block_id)
	REFERENCES Block (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE,
CONSTRAINT BlockViewAccess_id 
	FOREIGN KEY (UserGroup_id)
	REFERENCES UserGroup (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE
)
;


CREATE TABLE BlockEditAccess (
editable_from TIMESTAMP NOT NULL,
editable_to TIMESTAMP NULL,
Block_id INTEGER NOT NULL,
UserGroup_id INTEGER NOT NULL,

CONSTRAINT BlockEditAccess_PK
	PRIMARY KEY (Block_id,UserGroup_id),
CONSTRAINT BlockEditAccess_id 
	FOREIGN KEY (Block_id)
	REFERENCES Block (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE,
CONSTRAINT BlockEditAccess_id 
	FOREIGN KEY (UserGroup_id)
	REFERENCES UserGroup (id)
		ON DELETE NO ACTION
		ON UPDATE CASCADE
)
;
