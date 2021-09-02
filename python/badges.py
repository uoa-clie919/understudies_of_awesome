from datetime import date

class Badges:
    def __init__(self, customerID):
        self.badgeList = [False,False,False,False,False,False,False,False]
        

    def getBadge(self,position):
        return self.badgeList[position-1]

    def checkLogInBadge(self):
        if(not self.badgeList[0]):
            self.badgeList[0] = True

    def checkMilestoneBadge(self,points):
        if(not self.badgeList[1] and points>50):
            self.badgeList[1] = True


    def checkMilestone2Badge(self,points):
        if(not self.badgeList[2] and points>100):
            self.badgeList[2] = True

    def checkMilestone3Badge(self,points):
        if(not self.badgeList[3] and points>1000):
            self.badgeList[3] = True


    def checkXmasBadge(self):
        if(not self.badgeList[4]):
            today = str(date.today())
            today = today[5:9]
            if(today == '12-25'):
                self.badgeList[4] = True
        
