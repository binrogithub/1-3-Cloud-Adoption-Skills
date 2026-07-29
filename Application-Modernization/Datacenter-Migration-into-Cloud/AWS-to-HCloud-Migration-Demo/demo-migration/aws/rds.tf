resource "aws_db_subnet_group" "main" {
  name       = "demo-db-subnet-group"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = {
    Name = "demo-db-subnet-group"
  }
}

resource "aws_db_instance" "main" {
  identifier             = "demo-db"
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  storage_type           = "gp3"
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  multi_az               = false
  publicly_accessible    = false
  skip_final_snapshot    = true
  db_name                = "wordpress"
  username               = "admin"
  password               = "ChangeMe123!"

  tags = {
    Name = "demo-rds"
  }
}
